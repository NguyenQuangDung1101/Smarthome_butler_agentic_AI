import React, { useState, useEffect } from 'react';

const App = () => {
  const [activeTab, setActiveTab] = useState('tab1');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const response = await fetch('/api/appliances');
      const result = await response.json();
      if (result.success) {
        setData(result.data["List_of house appliance (current values)"]);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 2000); // poll every 2 seconds
    return () => clearInterval(interval);
  }, []);

  const openTab = (tabName) => {
    setActiveTab(tabName);
  };

  const updateDevice = async (espID, deviceID, valueType, inputId) => {
    const inputElement = document.getElementById(inputId);
    if (!inputElement) return;
    const rawValue = inputElement.value;
    let parsedValue;
    if (valueType === 'boolean') {
      parsedValue = rawValue === 'true';
    } else if (valueType === 'integer') {
      parsedValue = parseInt(rawValue, 10);
    } else {
      parsedValue = rawValue;
    }

    const statusDiv = document.getElementById(`status-${espID}-${deviceID}`);
    if (statusDiv) {
      statusDiv.style.color = '#007bff';
      statusDiv.innerText = 'Sending...';
    }

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
        if (statusDiv) {
          statusDiv.style.color = 'green';
          statusDiv.innerText = 'Success!';
        }
        // Refresh data
        fetchData();
      } else {
        if (statusDiv) {
          statusDiv.style.color = 'red';
          statusDiv.innerText = result.error || 'Error occurred';
        }
      }
    } catch (error) {
      if (statusDiv) {
        statusDiv.style.color = 'red';
        statusDiv.innerText = 'Network Error';
      }
    }

    setTimeout(() => {
      if (statusDiv && statusDiv.innerText === 'Success!') {
        statusDiv.innerText = '';
      }
    }, 3000);
  };

  const renderTab1Info = () => {
    if (loading) return <div>Loading devices...</div>;
    if (!data) return <div>No data available.</div>;

    return (
      <div id="tab1-nodes">
        {Object.entries(data).map(([roomName, roomData]) => {
          const espID = roomData.espID;
          const allDevices = [...(roomData.actuator || []), ...(roomData.sensor || [])];
          return (
            <div key={roomName} className="room-section">
              <h3 className="room-title">{roomName} (espID: {espID})</h3>
              <div className="nodes-grid">
                {allDevices.map(device => {
                  let displayValue = device.value;
                  if (device.value_type === 'boolean') {
                    displayValue = device.value ? 'On' : 'Off';
                  }
                  if (device.constraints && device.constraints.unit) {
                    displayValue += ` ${device.constraints.unit}`;
                  }
                  return (
                    <div key={device.id} className="node-card">
                      <div>
                        <div className="node-header">{device.description}</div>
                        <div className="node-id">ID: {device.id} | Type: {device.value_type}</div>
                      </div>
                      <div className="node-value">{displayValue}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderTab2Controls = () => {
    if (loading) return <div>Loading actuators...</div>;
    if (!data) return <div>No data available.</div>;

    return (
      <div id="tab2-nodes">
        {Object.entries(data).filter(([roomName, roomData]) => roomData.actuator && roomData.actuator.length > 0).map(([roomName, roomData]) => {
          const espID = roomData.espID;
          return (
            <div key={roomName} className="room-section">
              <h3 className="room-title">{roomName} (espID: {espID})</h3>
              <div className="nodes-grid">
                {roomData.actuator.map(device => {
                  const inputId = `input-${espID}-${device.id}`;
                  let inputHtml;
                  if (device.value_type === 'boolean') {
                    inputHtml = (
                      <select id={inputId} defaultValue={device.value.toString()}>
                        <option value="true">True (On)</option>
                        <option value="false">False (Off)</option>
                      </select>
                    );
                  } else if (device.value_type === 'integer') {
                    const min = device.constraints?.min ?? 0;
                    const max = device.constraints?.max ?? 100;
                    inputHtml = <input type="number" id={inputId} defaultValue={device.value} min={min} max={max} />;
                  }
                  return (
                    <div key={device.id} className="node-card">
                      <div>
                        <div className="node-header">{device.description}</div>
                        <div className="node-id">ID: {device.id} | Current: {device.value}</div>
                      </div>
                      <div className="control-input">
                        {inputHtml}
                      </div>
                      <button className="update-btn" onClick={() => updateDevice(espID, device.id, device.value_type, inputId)}>Update</button>
                      <div id={`status-${espID}-${device.id}`} className="status-msg"></div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="container">
      <h1>Smart Home Dashboard</h1>
      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'tab1' ? 'active' : ''}`} onClick={() => openTab('tab1')}>Device Information</button>
        <button className={`tab-btn ${activeTab === 'tab2' ? 'active' : ''}`} onClick={() => openTab('tab2')}>Manual Control</button>
        <button className={`tab-btn ${activeTab === 'tab3' ? 'active' : ''}`} onClick={() => openTab('tab3')}>AI Chat</button>
      </div>

      {activeTab === 'tab1' && (
        <div className="tab-content">
          <div className="header-action">
            <h2>Current Appliances Info</h2>
            <button className="refresh-btn" onClick={fetchData}>Refresh Data</button>
          </div>
          {renderTab1Info()}
        </div>
      )}

      {activeTab === 'tab2' && (
        <div className="tab-content">
          <div className="header-action">
            <h2>Control Actuators</h2>
            <button className="refresh-btn" onClick={fetchData}>Refresh Devices</button>
          </div>
          {renderTab2Controls()}
        </div>
      )}

      {activeTab === 'tab3' && (
        <div className="tab-content">
          <h2>Agentic AI Chat</h2>
          <div className="chat-box">
            <div className="chat-history">
              <p><em>AI: Hello! How can I manage your home today?</em></p>
            </div>
            <div className="chat-input-area">
              <input type="text" placeholder="Type a message..." disabled />
              <button disabled>Send</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
