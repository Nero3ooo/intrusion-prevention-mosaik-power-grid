// Called when page has loaded in browser
function initWebsocket() {
    console.log('Starting websocket...');

    // Save bandwidth by storing the ID of the last report of a violation
    let lastTimestamp = -1;
    let socket = new WebSocket("ws://localhost:8777");

    // event triggered when websocket is connected
    socket.onopen = function (e) {
        console.log("[#] Connection established.");
        // Periodically query for new reports of violations
        setInterval(function () {
            // Automatically retry connecting to C2 websocket when connection is lost / closed
            if (socket.readyState === WebSocket.CLOSED) {
                socket = new WebSocket("ws://localhost:8777");
                return;
            }
            
            // Create & send packet for querying new reports
            let reportsQueryText = '{ "type" : "query", "timestamp": ' + lastTimestamp + '}';
            socket.send(reportsQueryText);
        }, 500);
    };

    // Event called when reports are received
    socket.onmessage = function (event) {
        let newReports = JSON.parse(event.data);
        if (newReports.length > 0) {
            lastTimestamp = newReports[newReports.length - 1].timestamp;
        }

        // Add all reports in array to dashboard
        newReports.forEach(report => {
            addReportToDashboard(report);
        });
    };

    // Event called when connection has been closed
    socket.onclose = function (event) {
        if (event.wasClean) {
            console.log(`[-] Connection closed cleanly, code=${event.code} reason=${event.reason}`);
        } else {
            console.log('[-] Connection died');
        }
    };
    
    socket.onerror = function (error) {
        console.log(`[!] ${error}`);
    };
    
    function addReportToDashboard(report) {
        // Create report DOM element and add it to the left sidebar
        let reportWrapper = document.createElement('div');
        reportWrapper.classList.add('report');
        
        let violationTypeElem = document.createElement('div');
        violationTypeElem.classList.add('violation-type');
        violationTypeElem.innerHTML = report.requirement;
        
        let componentElem = document.createElement('div');
        componentElem.classList.add('component');
        
        let component = report.component_id;
        if (component.startsWith('branch_')) {
            component = "Branch " + report.component_id.substring(7);
        } else if (component.startsWith('sensor_')) {
            component = "Sensor " + report.component_id.substring(7);
        } else if (component.startsWith('b')) {
            component = "Bus " + report.component_id.substring(1);
        }
        
        componentElem.innerHTML = component;
        
        let timestampElem = document.createElement('div');
        timestampElem.classList.add('timestamp');
        timestampElem.innerHTML = convertTimestamp(report.timestamp);
        
        reportWrapper.appendChild(violationTypeElem);
        reportWrapper.appendChild(componentElem);
        reportWrapper.appendChild(timestampElem);
        
        let reportsFeed = document.querySelector('#reports-feed');
        
        reportsFeed.insertBefore(reportWrapper, document.querySelector('#reports-feed').firstChild);
        while (reportsFeed.children.length > 256) {
            reportsFeed.removeChild(reportsFeed.lastChild);
        }
        
        // Visually highlight component
        highlightComponent(report.component_id)
    }
    
    // Find SVG element based on the component id
    // Examples: branch_24, meter_3
    function highlightComponent(id) {
        if (!id.startsWith('branch_')) {
            let textElems = document.getElementsByTagName("text");
            let found = false;
            for (let i = 0; i < textElems.length; i++) {
                if (textElems[i].textContent == id) {
                    found = true;
                    
                    textElems[i].parentElement.firstChild.style.animation = 'none';
                    setTimeout(() => {
                        textElems[i].parentElement.firstChild.style.animation = null; 
                    }, 10);
                    textElems[i].parentElement.firstChild.classList.add('component--failure');
                    break;
                }
            }
            
            // Incase the map hasn't loaded yet, try again in a second
            if (!found) {
                setTimeout(() => {
                    highlightComponent(id);
                }, 1000);
            }
        } else {
            let linkElems = document.getElementsByTagName("line");
            let found = false;
            for (let i = 0; i < linkElems.length; i++) {
                if (linkElems[i].dataset.branch.startsWith(id)) {
                    linkElems[i].style.animation = 'none';
                    setTimeout(() => {
                        linkElems[i].style.animation = null; 
                    }, 10);
                    linkElems[i].classList.add('component--failure');
                    //linkElems[i].style.stroke = "rgba(220, 0, 0, 1)";
                    found = true;
                }
            }
            
            // Incase the map hasn't loaded yet, try again in a second
            if (!found) {
                setTimeout(() => {
                    highlightComponent(id);
                }, 1000);
            }
        }
    }

    function convertTimestamp(timestamp) {
        var date = new Date(timestamp * 1000);
        var hour = (date.getHours() < 10 ? '0' + date.getHours() : date.getHours());
        var min = (date.getMinutes() < 10 ? '0' + date.getMinutes() : date.getMinutes());
        var sec = (date.getSeconds() < 10 ? '0' + date.getSeconds() : date.getSeconds());
        var time = hour + ':' + min + ':' + sec;
        return time;
    }
}

window.addEventListener('load', function () {
    initWebsocket();
});