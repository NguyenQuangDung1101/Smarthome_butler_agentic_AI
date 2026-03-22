import React, { useState, useEffect, useCallback } from 'react';
import ChatTab from './ChatTab.jsx';
import NotesTab from './NotesTab.jsx';
import ScheduleTab from './ScheduleTab.jsx';
import ScheduleSessionTab from './ScheduleSessionTab.jsx';
import logoUrl from './assets/logo_Beyondblue.png';

const App = () => {
  const [activeTab, setActiveTab] = useState('tab1');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pendingPermissions, setPendingPermissions] = useState(0);
  const [showBellPopup, setShowBellPopup] = useState(false);

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

    // Index rooms by espID for fixed house layout
    const roomsByEsp = {};
    Object.entries(data).forEach(([roomName, roomData]) => {
      roomsByEsp[roomData.espID] = { roomName, roomData };
    });

    const renderRoomBlock = (espID) => {
      const entry = roomsByEsp[espID];
      if (!entry) return null;
      const { roomName, roomData } = entry;
      const allDevices = [...(roomData.actuator || []), ...(roomData.sensor || [])];
      return (
        <div className="house-room">
          <h3 className="room-title">
            {roomName} <span style={{ fontSize: '0.72em', opacity: 0.55, fontWeight: 400 }}>ESP{espID}</span>
          </h3>
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
    };

    return (
      <div className="house-layout">
        <div className="house-top-row">
          {renderRoomBlock(1)}
          {renderRoomBlock(3)}
        </div>
        <div className="house-bottom-row">
          {renderRoomBlock(2)}
        </div>
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
                  const labelId = `label-${espID}-${device.id}`;

                  if (device.value_type === 'boolean') {
                    return (
                      <div key={device.id} className="node-card">
                        <div>
                          <div className="node-header">{device.description}</div>
                          <div className="node-id">ID: {device.id} | Current: {device.value ? 'On' : 'Off'}</div>
                        </div>
                        {/* hidden input so updateDevice can read the chosen value */}
                        <input type="hidden" id={inputId} defaultValue={device.value.toString()} />
                        <div className="bool-btn-group">
                          <button
                            className={`bool-btn bool-on${device.value === true ? ' active' : ''}`}
                            onClick={() => {
                              const el = document.getElementById(inputId);
                              if (el) el.value = 'true';
                              updateDevice(espID, device.id, device.value_type, inputId);
                            }}
                          >On</button>
                          <button
                            className={`bool-btn bool-off${device.value === false ? ' active' : ''}`}
                            onClick={() => {
                              const el = document.getElementById(inputId);
                              if (el) el.value = 'false';
                              updateDevice(espID, device.id, device.value_type, inputId);
                            }}
                          >Off</button>
                        </div>
                        <div id={`status-${espID}-${device.id}`} className="status-msg"></div>
                      </div>
                    );
                  }

                  if (device.value_type === 'integer') {
                    const min = device.constraints?.min ?? 0;
                    const max = device.constraints?.max ?? 100;
                    return (
                      <div key={device.id} className="node-card">
                        <div>
                          <div className="node-header">{device.description}</div>
                          <div className="node-id">ID: {device.id} | Current: {device.value}</div>
                        </div>
                        <div className="slider-wrapper">
                          <input
                            type="range"
                            id={inputId}
                            defaultValue={device.value}
                            min={min}
                            max={max}
                            onChange={e => {
                              const lbl = document.getElementById(labelId);
                              if (lbl) lbl.textContent = e.target.value;
                            }}
                          />
                          <span id={labelId} className="slider-value">{device.value}</span>
                        </div>
                        <button className="update-btn" onClick={() => updateDevice(espID, device.id, device.value_type, inputId)}>Update</button>
                        <div id={`status-${espID}-${device.id}`} className="status-msg"></div>
                      </div>
                    );
                  }

                  return null;
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
      {/* ── Notification Bell ── */}
      <div className="notif-bell-wrapper">
        <button
          className={`notif-bell-btn${pendingPermissions > 0 ? ' has-notif' : ''}`}
          onClick={() => { setShowBellPopup(p => !p); if (pendingPermissions > 0) setActiveTab('tab6'); }}
          title="Pending permission requests"
        >
          🔔
          {pendingPermissions > 0 && (
            <span className="notif-bell-count">{pendingPermissions}</span>
          )}
        </button>
        {showBellPopup && pendingPermissions === 0 && (
          <div className="notif-popup">No pending notifications</div>
        )}
      </div>

      <div className="site-header">
        <img src={logoUrl} alt="BEON logo" className="site-logo" />
        <h1>BEON - Smart Home Butler</h1>
      </div>
      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'tab1' ? 'active' : ''}`} onClick={() => openTab('tab1')}>Device Information</button>
        <button className={`tab-btn ${activeTab === 'tab2' ? 'active' : ''}`} onClick={() => openTab('tab2')}>Manual Control</button>
        <button className={`tab-btn ${activeTab === 'tab3' ? 'active' : ''}`} onClick={() => openTab('tab3')}>User Chat Session</button>
        <button className={`tab-btn ${activeTab === 'tab4' ? 'active' : ''}`} onClick={() => openTab('tab4')}>Notes</button>
        <button className={`tab-btn ${activeTab === 'tab5' ? 'active' : ''}`} onClick={() => openTab('tab5')}>Schedules</button>
        <button className={`tab-btn ${activeTab === 'tab6' ? 'active' : ''}`} onClick={() => openTab('tab6')}>
          Schedule Session
          {pendingPermissions > 0 && <span className="tab-notif-dot">{pendingPermissions}</span>}
        </button>
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
          </div>
          {renderTab2Controls()}
        </div>
      )}

      {activeTab === 'tab3' && <ChatTab />}

      {activeTab === 'tab4' && <NotesTab />}

      {activeTab === 'tab5' && <ScheduleTab />}

      {activeTab === 'tab6' && (
        <ScheduleSessionTab onPendingPermissionsChange={setPendingPermissions} />
      )}
    </div>
  );
};

export default App;
