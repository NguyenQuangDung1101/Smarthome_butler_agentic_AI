let deviceMapping = {};

// --- Tab Switching Logic ---
function openTab(evt, tabName) {
    let i, tabcontent, tablinks;
    
    tabcontent = document.getElementsByClassName("tab-content");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].classList.remove("active");
    }
    
    tablinks = document.getElementsByClassName("tab-btn");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].classList.remove("active");
    }
    
    document.getElementById(tabName).classList.add("active");
    evt.currentTarget.classList.add("active");

    if (tabName === 'tab1') loadAppliances();
}

// --- Tab 1: Load JSON Data ---
async function loadAppliances() {
    const display = document.getElementById("appliance-data-display");
    try {
        const response = await fetch('/api/appliances');
        const result = await response.json();
        if (result.success) {
            display.textContent = JSON.stringify(result.data, null, 2);
        } else {
            display.textContent = "Error loading data.";
        }
    } catch (error) {
        display.textContent = "Fetch error: " + error;
    }
}

// --- Tab 2: Manual Control Logic ---
async function loadDeviceMapping() {
    try {
        const response = await fetch('/api/device_mapping');
        deviceMapping = await response.json();
        
        const espSelect = document.getElementById("espID");
        for (const esp in deviceMapping) {
            let opt = document.createElement("option");
            opt.value = esp;
            opt.textContent = "ESP ID: " + esp;
            espSelect.appendChild(opt);
        }
    } catch (error) {
        console.error("Failed to load mapping", error);
    }
}

function updateDeviceDropdown() {
    const espID = document.getElementById("espID").value;
    const deviceSelect = document.getElementById("device_name");
    deviceSelect.innerHTML = '<option value="">Select Device...</option>';
    document.getElementById("value-input-container").innerHTML = '<input type="text" disabled placeholder="Select a device first">';

    if (!espID) return;

    const devices = deviceMapping[espID];
    for (const dev in devices) {
        let opt = document.createElement("option");
        opt.value = dev;
        opt.textContent = dev + " (" + devices[dev] + ")";
        deviceSelect.appendChild(opt);
    }
}

function updateValueInput() {
    const espID = document.getElementById("espID").value;
    const deviceName = document.getElementById("device_name").value;
    const container = document.getElementById("value-input-container");

    if (!espID || !deviceName) {
        container.innerHTML = '<input type="text" disabled placeholder="Select a device first">';
        return;
    }

    const type = deviceMapping[espID][deviceName];
    if (type === "boolean") {
        container.innerHTML = `
            <select id="device_value">
                <option value="true">True (On)</option>
                <option value="false">False (Off)</option>
            </select>
        `;
    } else if (type === "integer") {
        container.innerHTML = `<input type="number" id="device_value" placeholder="Enter number 0-100" min="0" max="100">`;
    }
}

async function sendControlCommand() {
    const espID = document.getElementById("espID").value;
    const device_name = document.getElementById("device_name").value;
    const valueInput = document.getElementById("device_value");
    const resultDiv = document.getElementById("control-result");

    if (!espID || !device_name || !valueInput) {
        resultDiv.innerHTML = "<span style='color:red'>Please fill all fields.</span>";
        return;
    }

    let val = valueInput.value;
    const type = deviceMapping[espID][device_name];
    
    // Parse value correctly
    if (type === "boolean") {
        val = (val === "true");
    } else if (type === "integer") {
        val = parseInt(val, 10);
    }

    resultDiv.innerHTML = "Sending...";

    try {
        const response = await fetch('/api/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ espID: espID, device_name: device_name, value: val })
        });
        
        const result = await response.json();
        if (result.success) {
            resultDiv.innerHTML = `<span style='color:green'>Success!</span><pre>${JSON.stringify(result.payload, null, 2)}</pre>`;
        } else {
            resultDiv.innerHTML = `<span style='color:red'>Error: ${result.error}</span>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<span style='color:red'>Network Error: ${error}</span>`;
    }
}

// Init
window.onload = () => {
    loadAppliances();
    loadDeviceMapping();
};