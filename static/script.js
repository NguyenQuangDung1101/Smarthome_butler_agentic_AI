// --- Tab Switching Logic ---
function openTab(evt, tabName) {
    let tabcontent = document.getElementsByClassName("tab-content");
    for (let i = 0; i < tabcontent.length; i++) {
        tabcontent[i].classList.remove("active");
    }
    
    let tablinks = document.getElementsByClassName("tab-btn");
    for (let i = 0; i < tablinks.length; i++) {
        tablinks[i].classList.remove("active");
    }
    
    document.getElementById(tabName).classList.add("active");
    evt.currentTarget.classList.add("active");
}

// --- Fetch Data and Render Nodes ---
async function fetchAndRenderData() {
    try {
        const response = await fetch('/api/appliances');
        const result = await response.json();
        
        if (result.success) {
            const data = result.data["List_of house appliance (current values)"];
            renderTab1Info(data);
            renderTab2Controls(data);
        } else {
            document.getElementById('tab1-nodes').innerText = "Error loading data.";
            document.getElementById('tab2-nodes').innerText = "Error loading data.";
        }
    } catch (error) {
        console.error("Fetch error:", error);
    }
}

// --- Render Tab 1: Info Nodes ---
function renderTab1Info(data) {
    const container = document.getElementById('tab1-nodes');
    container.innerHTML = ''; // Clear old data

    for (const [roomName, roomData] of Object.entries(data)) {
        const espID = roomData.espID;
        
        const roomSection = document.createElement('div');
        roomSection.className = 'room-section';
        roomSection.innerHTML = `<h3 class="room-title">${roomName} (espID: ${espID})</h3>`;
        
        const grid = document.createElement('div');
        grid.className = 'nodes-grid';

        // Combine Actuators and Sensors for display
        const allDevices = [...(roomData.actuator || []), ...(roomData.sensor || [])];

        allDevices.forEach(device => {
            let displayValue = device.value;
            // Add unit if present in constraints
            if (device.constraints && device.constraints.unit) {
                displayValue += ` ${device.constraints.unit}`;
            }

            const card = document.createElement('div');
            card.className = 'node-card';
            card.innerHTML = `
                <div>
                    <div class="node-header">${device.description}</div>
                    <div class="node-id">ID: ${device.id} | Type: ${device.value_type}</div>
                </div>
                <div class="node-value">${displayValue}</div>
            `;
            grid.appendChild(card);
        });

        roomSection.appendChild(grid);
        container.appendChild(roomSection);
    }
}

// --- Render Tab 2: Control Nodes ---
function renderTab2Controls(data) {
    const container = document.getElementById('tab2-nodes');
    container.innerHTML = ''; // Clear old data

    for (const [roomName, roomData] of Object.entries(data)) {
        const espID = roomData.espID;
        
        // Only Actuators can be controlled
        if (!roomData.actuator || roomData.actuator.length === 0) continue;

        const roomSection = document.createElement('div');
        roomSection.className = 'room-section';
        roomSection.innerHTML = `<h3 class="room-title">${roomName} (espID: ${espID})</h3>`;
        
        const grid = document.createElement('div');
        grid.className = 'nodes-grid';

        roomData.actuator.forEach(device => {
            const card = document.createElement('div');
            card.className = 'node-card';
            
            // Build input field based on value_type
            let inputHtml = '';
            let inputId = `input-${espID}-${device.id}`;
            
            if (device.value_type === 'boolean') {
                inputHtml = `
                    <select id="${inputId}">
                        <option value="true" ${device.value === true ? 'selected' : ''}>True (On)</option>
                        <option value="false" ${device.value === false ? 'selected' : ''}>False (Off)</option>
                    </select>
                `;
            } else if (device.value_type === 'integer') {
                let min = device.constraints.min !== undefined ? device.constraints.min : 0;
                let max = device.constraints.max !== undefined ? device.constraints.max : 100;
                inputHtml = `<input type="number" id="${inputId}" value="${device.value}" min="${min}" max="${max}">`;
            }

            card.innerHTML = `
                <div>
                    <div class="node-header">${device.description}</div>
                    <div class="node-id">ID: ${device.id} | Current: ${device.value}</div>
                </div>
                <div class="control-input">
                    ${inputHtml}
                </div>
                <button class="update-btn" onclick="updateDevice(${espID}, '${device.id}', '${device.value_type}', '${inputId}')">Update</button>
                <div id="status-${espID}-${device.id}" class="status-msg"></div>
            `;
            grid.appendChild(card);
        });

        roomSection.appendChild(grid);
        container.appendChild(roomSection);
    }
}

// --- Handle Update Action ---
async function updateDevice(espID, deviceID, valueType, inputId) {
    const statusDiv = document.getElementById(`status-${espID}-${deviceID}`);
    const rawValue = document.getElementById(inputId).value;
    
    // CAREFUL WITH DATATYPE: Parse value correctly before sending
    let parsedValue;
    if (valueType === 'boolean') {
        parsedValue = (rawValue === 'true');
    } else if (valueType === 'integer') {
        parsedValue = parseInt(rawValue, 10);
    } else {
        parsedValue = rawValue;
    }

    statusDiv.style.color = '#007bff';
    statusDiv.innerText = 'Sending...';

    try {
        const response = await fetch('/api/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                espID: espID,
                device_name: deviceID,
                value: parsedValue
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            statusDiv.style.color = 'green';
            statusDiv.innerText = 'Success!';
            // Tùy chọn: Tự động refresh lại dữ liệu sau khi update thành công
            // setTimeout(() => fetchAndRenderData(), 1000); 
        } else {
            statusDiv.style.color = 'red';
            statusDiv.innerText = result.error || 'Error occurred';
        }
    } catch (error) {
        statusDiv.style.color = 'red';
        statusDiv.innerText = 'Network Error';
    }
    
    // Clear message after 3 seconds
    setTimeout(() => {
        if(statusDiv.innerText === 'Success!') statusDiv.innerText = '';
    }, 3000);
}

// Initialize data when page loads
window.onload = () => {
    fetchAndRenderData();
};