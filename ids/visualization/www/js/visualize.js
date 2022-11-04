import * as d3 from 'https://cdn.skypack.dev/d3@7';

var svg = d3.select("#svg-graph")

// SVG objects
var branchComponent, busComponent, meterComponent, switchComponent;

fetch('./graph.json')
  .then(response => response.json())
  .then(graph => {
    
    
    // Convert into cola.js format
    let branches = graph.links;
    let nodes = graph.nodes;
    for (let branchIndex = 0; branchIndex < branches.length; branchIndex++) {
      let branch = branches[branchIndex];
      for (let nodeIndex = 0; nodeIndex < nodes.length; nodeIndex++) {
        let node = nodes[nodeIndex];
        if (branch.source === node.id)
          branch.source = node;
        if (branch.target === node.id)
          branch.target = node;
      }
    }
    
    // Randomly generate color for each grid
    let gridColorPicker = d3.scaleOrdinal().domain([0, graph.rtu_count]).range(d3.schemeSet2);
    let subgridColorDictionary = {}; 
    
    // Create triangle shape for switch components
    let switchTriangle = d3.symbol()
      .type(d3.symbolTriangle)
      .size(120);

    // Create DOM elements for all graph components
    function initializeDisplay() {
      let setupBranches = function () {
        // Link lines: set the data and propertie
        branchComponent = svg.append("g")
          .attr("class", "links")
          .selectAll("line")
          .data(graph.links)
          .enter()
          .append("line")
          .attr("stroke-width", 1)
          .attr("data-branch", function (d) { return d.identifier; });
      }

      let setupBusses = function () {
        // Bus: set the data and properties
        busComponent = svg.append("g")
          .attr("class", "busses")
          .selectAll("g")
          .data(graph.nodes.filter(elem => elem.type == "bus"))
          .enter()
          .append("g");

        // Bus: shape
        busComponent
          .append("circle")
          .attr("fill", "white")
          .attr("r", 10)
          .style("stroke", function (d) {
            subgridColorDictionary[d.rtu] = gridColorPicker(d.rtu);
            return subgridColorDictionary[d.rtu];
          });

        // Bus: label
        busComponent.append("text")
          .attr("transform", "translate(0,2.5)")
          .attr("font-size", "8")
          .style("text-anchor", "middle")
          .text(function (d) { return d.id })
      }

      let setupMeters = function () {
        // Meters: set data and properties
        meterComponent = svg.append("g")
          .attr("class", "meters")
          .selectAll("g")
          .data(graph.nodes.filter(elem => elem.type == "meter"))
          .enter()
          .append("g");


        // Meters: shape
        meterComponent
          .append("rect")
          .attr("fill", "white")
          .style("stroke", function (d) {
            subgridColorDictionary[d.rtu] = gridColorPicker(d.rtu);
            return subgridColorDictionary[d.rtu];
          })
          .attr("width", 40)
          .attr("height", 12)
          .attr("transform", "translate(-20, -6)")
          .attr("rx", 2)
          .attr("ry", 2);

        // Meters: label
        meterComponent
          .append("text")
          .attr("font-size", "8")
          .attr("transform", "translate(0, 2.5)")
          .style("text-anchor", "middle")
          .text(function (d) { return d.id });
      }

      let setupSwitches = function () {
        // Switches: set data and properties
        switchComponent = svg.append("g")
          .attr("class", "switches")
          .selectAll("g")
          .data(graph.nodes.filter(elem => elem.type == "switch"))
          .enter()
          .append("g");

        // Switches: shape
        switchComponent
          .append("path")
          .attr("d", switchTriangle)
          .attr("fill", "white")
          .style("stroke", function (d) {
            subgridColorDictionary[d.rtu] = gridColorPicker(d.rtu);
            return subgridColorDictionary[d.rtu];
          });

        // Switches: label
        switchComponent.append("text")
          .attr("font-size", "8")
          .style("text-anchor", "middle")
          .attr("transform", "translate(0, 2.5)")
          .text(function (d) { return d.id });
      }

      setupBranches();
      setupBusses();
      setupMeters();
      setupSwitches();

      // Setup graph legend with the generated colors and component symbols
      let groupsContainer = document.querySelector('.legend-groups');
      for (let subgridIndex = 0; subgridIndex < graph.rtu_count; subgridIndex++) {
        let groupContainerElement = document.createElement('div');
        groupContainerElement.classList.add('group-item');

        let subgridColorElement = document.createElement('div');
        subgridColorElement.classList.add('group-color');
        subgridColorElement.style.backgroundColor = subgridColorDictionary[subgridIndex];

        let subgridLabelElement = document.createElement('div');
        subgridLabelElement.classList.add('group-label');
        subgridLabelElement.innerHTML = 'Subgrid ' + (subgridIndex + 1);

        groupContainerElement.append(subgridColorElement);
        groupContainerElement.append(subgridLabelElement);
        groupsContainer.append(groupContainerElement);
      }
    }


    // Move DOM elements to their generated positions
    // (called once cola.js generated the graph)
    function setPositions() {
      branchComponent.attr("x1", function (d) { return d.source.x; })
        .attr("y1", function (d) { return d.source.y; })
        .attr("x2", function (d) { return d.target.x; })
        .attr("y2", function (d) { return d.target.y; });
        
      busComponent.attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ")"; });
      meterComponent.attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ")"; });
      switchComponent.attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ")"; });
    }

    // Create graph with cola.js
    let d3cola = cola.d3adaptor()
      .linkDistance(100)
      .size([svg.node().getBoundingClientRect().width, svg.node().getBoundingClientRect().height])
      .nodes(graph.nodes)
      .links(graph.links)
      .symmetricDiffLinkLengths(13)
      .avoidOverlaps(true)
      .start(10, 15, 20)
      .on('end', function () {
        document.querySelector('#loading').classList.add('loaded');
        initializeDisplay();
        setPositions();
        svgPanZoom('#svg-graph', {
          viewportSelector: '#svg-container',
          panEnabled: true,
          controlIconsEnabled: false,
          zoomEnabled: true,
          dblClickZoomEnabled: true,
          mouseWheelZoomEnabled: true,
          preventMouseEventsDefault: true,
          zoomScaleSensitivity: 0.2,
          minZoom: 0.5,
          maxZoom: 10,
          fit: true,
          contain: false,
          center: true,
          refreshRate: 60,
          onZoom: function (scale) {
            document.querySelector('#controls-zoom').innerHTML = (Math.round(scale * 100)) + '%';
          },
          customEventsHandler: {
            init: function (options) {
              options.instance.zoomBy(0.9);
              options.instance.panBy({
                x: 150,
                y: 0 
              });
              
              document.querySelector('#controls-zoom').innerHTML = (Math.round(options.instance.getZoom() * 100)) + '%';

              document.querySelector('#controls-zoom-in').addEventListener('click', function () {
                options.instance.zoomBy(1.2);
              });
              document.querySelector('#controls-zoom-out').addEventListener('click', function () {
                options.instance.zoomBy(0.8);
              });
              /*document.querySelector('#controls-zoom-reset').addEventListener('click', function () {
                options.instance.resetZoom();
                options.instance.fit();
                options.instance.zoomBy(0.7);
                options.instance.center();
                options.instance.panBy({
                  x: 150,
                  y: 0 
                });
              });*/
            }
          }
        });
      });
  });
