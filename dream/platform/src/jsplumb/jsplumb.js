/* ===========================================================================
 * Copyright 2013 Nexedi SA and Contributors
 *
 * This file is part of DREAM.
 *
 * DREAM is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * DREAM is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with DREAM.  If not, see <http://www.gnu.org/licenses/>.
 * ==========================================================================*/

/*global RSVP, rJS, $, jsPlumb, Handlebars, initGadgetMixin,
  loopEventListener, promiseEventListener, DOMParser, confirm */
/*jslint unparam: true todo: true */
(function (RSVP, rJS, $, jsPlumb, Handlebars, initGadgetMixin,
           loopEventListener, promiseEventListener, DOMParser) {
  "use strict";

  /*jslint nomen: true */
  var gadget_klass = rJS(window),
    node_template_source = gadget_klass.__template_element
      .getElementById('node-template').innerHTML,
    node_template = Handlebars.compile(node_template_source),
    popup_edit_template = gadget_klass.__template_element
       .getElementById('popup-edit-template'),
    domParser = new DOMParser();

  function loopJsplumbBind(gadget, type, callback) {
    //////////////////////////
    // Infinite event listener (promise is never resolved)
    // eventListener is removed when promise is cancelled/rejected
    //////////////////////////
    var handle_event_callback,
      callback_promise,
      jsplumb_instance = gadget.props.jsplumb_instance;

    function cancelResolver() {
      if ((callback_promise !== undefined) &&
          (typeof callback_promise.cancel === "function")) {
        callback_promise.cancel();
      }
    }

    function canceller() {
      if (handle_event_callback !== undefined) {
        jsplumb_instance.unbind(type);
      }
      cancelResolver();
    }

    function resolver(resolve, reject) {

      handle_event_callback = function () {
        var args = arguments;
        cancelResolver();
        callback_promise = new RSVP.Queue()
          .push(function () {
            return callback.apply(jsplumb_instance, args);
          })
          .push(undefined, function (error) {
            if (!(error instanceof RSVP.CancellationError)) {
              canceller();
              reject(error);
            }
          });
      };

      jsplumb_instance.bind(type, handle_event_callback);
    }
    return new RSVP.Promise(resolver, canceller);
  }

  function getNodeId(gadget, element_id) {
    // returns the ID of the node in the graph from its DOM element id
    var node_id;
    $.each(gadget.props.node_id_to_dom_element_id, function (k, v) {
      if (v === element_id) {
        node_id = k;
        return false;
      }
    });
    return node_id;
  }

  function generateNodeId(gadget, element) {
    // Generate a node id
    var n = 1,
      class_def = gadget.props.data.class_definition[element._class],
      id = class_def.short_id || element._class;
    while (gadget.props.data.graph.node[id + n] !== undefined) {
      n += 1;
    }
    return id + n;
  }

  function generateDomElementId(gadget_element) {
    // Generate a probably unique DOM element ID.
    var n = 1;
    while ($(gadget_element).find('#DreamNode_' + n).length > 0) {
      n += 1;
    }
    return 'DreamNode_' + n;
  }

  function updateConnectionData(gadget, connection, remove, edge_data) {
    if (remove) {
      delete gadget.props.data.graph.edge[connection.id];
    } else {
      edge_data = edge_data || {'_class': 'Dream.Edge'};
      edge_data.source = getNodeId(gadget, connection.sourceId);
      edge_data.destination = getNodeId(gadget, connection.targetId);
      gadget.props.data.graph.edge[connection.id] = edge_data;
    }
    gadget.notifyDataChanged();
  }

  // bind to connection/connectionDetached events,
  // and update the list of connections on screen.

  function waitForConnection(gadget) {
    loopJsplumbBind(gadget, 'connection',
                    function (info, originalEvent) {
        updateConnectionData(gadget, info.connection);
      });
  }

  function waitForConnectionDetached(gadget) {
    loopJsplumbBind(gadget, 'connectionDetached',
                    function (info, originalEvent) {
        updateConnectionData(gadget, info.connection, true);
      });
  }

  function waitForConnectionClick(gadget) {
    // TODO: dialog to edit connection properties
    loopJsplumbBind(gadget, 'click', function (connection) {
      if (confirm("Delete connection ?")) {
        gadget.props.jsplumb_instance.detach(connection);
      }
    });
  }

  function convertToAbsolutePosition(gadget, x, y) {
    var zoom_level = gadget.props.zoom_level * 1.1111,
      canvas_size_x = $(gadget.props.main).width(),
      canvas_size_y = $(gadget.props.main).height(),
      size_x = $(gadget.props.element).find('.dummy_window').width() *
        zoom_level,
      size_y = $(gadget.props.element).find('.dummy_window').height() *
        zoom_level,
      top = Math.floor(y * (canvas_size_y - size_y)) + "px",
      left = Math.floor(x * (canvas_size_x - size_x)) + "px";
    return [left, top];
  }

  function convertToRelativePosition(gadget, x, y) {
    var zoom_level = gadget.props.zoom_level * 1.1111,
      canvas_size_x = $(gadget.props.main).width(),
      canvas_size_y = $(gadget.props.main).height(),
      size_x = $(gadget.props.element).find('.dummy_window').width() *
        zoom_level,
      size_y = $(gadget.props.element).find('.dummy_window').height() *
        zoom_level,
      top = Math.max(Math.min(y.replace('px', '') /
                              (canvas_size_y - size_y), 1), 0),
      left = Math.max(Math.min(x.replace('px', '') /
                               (canvas_size_x - size_x), 1), 0);
    return [left, top];
  }

  function updateElementCoordinate(gadget, node_id, coordinate) {
    var element_id = gadget.props.node_id_to_dom_element_id[node_id],
      element,
      relative_position;

    if (coordinate === undefined) {
      element = $(gadget.props.element).find("#" + element_id);
      relative_position = convertToRelativePosition(
        gadget,
        element.css('left'),
        element.css('top')
      );
      coordinate = {
        left: relative_position[0],
        top: relative_position[1]
      };
    }

    gadget.props.data.graph.node[node_id].coordinate = coordinate;
    gadget.notifyDataChanged();
    return coordinate;
  }

  function draggable(gadget) {
    var jsplumb_instance = gadget.props.jsplumb_instance,
      stop = function (element) {
        updateElementCoordinate(gadget, getNodeId(gadget, element.target.id));
      };

    jsplumb_instance
      .draggable(jsplumb_instance.getSelector(".window"), {
        containment: 'parent',
        grid: [10, 10],
        stop: stop // FIXME: we should only accept if dropped in #main
      });

    jsplumb_instance
      .makeSource(jsplumb_instance.getSelector(".window"), {
        filter: ".ep",
        anchor: "Continuous",
        connector: ["StateMachine", {
          curviness: 20
        }],
        connectorStyle: {
          strokeStyle: "#5c96bc",
          lineWidth: 2,
          outlineColor: "transparent",
          outlineWidth: 4
        }
      });

    jsplumb_instance
      .makeTarget(jsplumb_instance.getSelector(".window"), {
        dropOptions: {
          hoverClass: "dragHover"
        },
        anchor: "Continuous"
      });
  }

  function initJsPlumb(gadget) {
    var jsplumb_instance = gadget.props.jsplumb_instance;

    jsplumb_instance.setRenderMode(jsplumb_instance.SVG);
    jsplumb_instance.importDefaults({
      HoverPaintStyle: {
        strokeStyle: "#1e8151",
        lineWidth: 2
      },
      Endpoint: ["Dot", {
        radius: 2
      }],
      ConnectionOverlays: [
        ["Arrow", {
          location: 1,
          id: "arrow",
          length: 14,
          foldback: 0.8
        }]
      ],
      Container: "main"
    });

    // listen for clicks on connections,
    // and offer to change values on click.

    // jsplumb_instance
    //   .bind("connectionDrag", function (connection) {
    //     return undefined;
    //   });

    // jsplumb_instance
    //   .bind("connectionDragStop", function (connection) {
    //     return undefined;
    //   });
    // split in 2 methods ? one for events one for manip

    gadget.notifyDataChanged();
    draggable(gadget);
  }

  function updateNodeStyle(gadget, element_id) {
    // Update node size according to the zoom level
    // XXX does nothing for now
    var zoom_level = gadget.props.zoom_level * 1.1111,
      element = $(gadget.props.element).find("#" + element_id),
      new_value;
    $.each(gadget.props.style_attr_list, function (i, j) {
      new_value = $(gadget.props.element).find('.dummy_window').css(j)
        .replace('px', '') * zoom_level + 'px';
      element.css(j, new_value);
    });
  }

  // function redraw(gadget) {
  //   var coordinates = gadget.props.preference_container.coordinates || {},
  //     absolute_position,
  //     element;
  //   $.each(coordinates, function (node_id, v) {
  //     absolute_position = convertToAbsolutePosition(
  //       gadget,
  //       v.left,
  //       v.top
  //     );
  //     element = $(gadget.props.element).find(
  //       '#' + gadget.props.node_id_to_dom_element_id[node_id];
  //     );
  //     element.css('top', absolute_position[1]);
  //     element.css('left', absolute_position[0]);
  //     gadget.props.jsplumb_instance.repaint(element);
  //   });
  // }

  // function positionGraph(gadget) {
  //   $.ajax(
  //     '/positionGraph',
  //     {
  //       data: JSON.stringify(getData()),
  //       contentType: 'application/json',
  //       type: 'POST',
  //       success: function (data, textStatus, jqXHR) {
  //         $.each(data, function (node, pos) {
  //           convertToAbsolutePosition(
  //             gadget,
  //             pos.left,
  //             pos.top
  //           );
  //           updateElementCoordinate(gadget, node, {
  //             top: pos.top,
  //             left: pos.left
  //           });
  //         });
  //         redraw(gadget);
  //       }
  //     }
  //   );
  // }


  function removeElement(gadget, node_id) {
    var element_id = gadget.props.node_id_to_dom_element_id[node_id];
    gadget.props.jsplumb_instance.removeAllEndpoints(
      $(gadget.props.element).find("#" + element_id)
    );
    $(gadget.props.element).find("#" + element_id).remove();
    delete gadget.props.data.graph.node[node_id];

    $.each(gadget.props.data.graph.edge, function (k, v) {
      if (node_id === v.source || node_id === v.destination) {
        delete gadget.props.data.graph.edge[k];
      }
    });

    gadget.notifyDataChanged();
  }

  function updateElementData(gadget, node_id, data) {
    var element_id = gadget.props.node_id_to_dom_element_id[node_id],
      new_id = data.id;
    if (data.data.name) {
      $(gadget.props.element).find("#" + element_id).text(data.data.name)
        .attr("title", data.data.name)
        .append('<div class="ep"></div></div>');
      gadget.props.data.graph.node[node_id].name = data.data.name;
    }
    delete data.id;
    $.extend(gadget.props.data.graph.node[node_id], data.data);
    if (new_id && new_id !== node_id) {
      gadget.props.data.graph.node[new_id]
        = gadget.props.data.graph.node[node_id];
      delete gadget.props.data.graph.node[node_id];

      gadget.props.node_id_to_dom_element_id[new_id]
        = gadget.props.node_id_to_dom_element_id[node_id];
      delete gadget.props.node_id_to_dom_element_id[node_id];

      delete gadget.props.data.graph.node[new_id].id;
      $.each(gadget.props.data.graph.edge, function (k, v) {
        if (v.source === node_id) {
          v.source = new_id;
        }
        if (v.destination === node_id) {
          v.destination = new_id;
        }
      });
    }
    gadget.notifyDataChanged();
  }

  function addEdge(gadget, edge_id, edge_data) {
    var overlays = [],
      connection;

    if (edge_data.name) {
      overlays = [["Label", {
        cssClass: "l1 component label",
        label: edge_data.name
      }]];
    }

    // If an edge has this data:
    // { _class: 'Edge',
    //   source: 'N1',
    //   destination: 'N2',
    //   jsplumb_source_endpoint: 'BottomCenter',
    //   jsplumb_destination_endpoint: 'LeftMiddle',
    //   jsplumb_connector: 'Flowchart' }
    // Then it is rendered using a flowchart connector. The difficulty is that
    // jsplumb does not let you configure the connector type on the edge, but
    // on the source endpoint. One solution seem to create all types of
    // endpoints on nodes.
    if ( edge_data.jsplumb_connector === 'Flowchart' ) {
        connection = gadget.props.jsplumb_instance.connect({
            uuids: [edge_data.source + ".flowChart" +
                         edge_data.jsplumb_source_endpoint,
                    edge_data.destination + ".flowChart" +
                         edge_data.jsplumb_destination_endpoint],
            overlays: overlays
        });
    } else {
      connection = gadget.props.jsplumb_instance.connect({
        source: gadget.props.node_id_to_dom_element_id[edge_data.source],
        target: gadget.props.node_id_to_dom_element_id[edge_data.destination],
        Connector: [ "Bezier", {curviness: 75} ],
        overlays: overlays
      });
    }

    // jsplumb assigned an id, but we are controlling ids ourselves.
    connection.id = edge_id;
  }

  function expandSchema(class_definition, full_schema) {
    // minimal expanding of json schema, supports merging allOf and $ref
    // references
    // TODO: check for a library with full support
    var property, referenced, i,
      expanded_class_definition = {properties:
        class_definition.properties || {}};
    if (class_definition.allOf) {
      for (i = 0; i < class_definition.allOf.length; i += 1) {
        referenced = class_definition.allOf[i];
        if (referenced.$ref) {
          referenced = expandSchema(
            full_schema.class_definition[
              referenced.$ref.substr(1, referenced.$ref.length)
            ],
            full_schema);
        }
        if (referenced.properties) {
          for (property in referenced.properties) {
            if (referenced.properties.hasOwnProperty(property)) {
              if (referenced.properties[property].type) {
                expanded_class_definition.properties[property]
                  = referenced.properties[property];
              }
            }
          }
        }
      }
    }
    return expanded_class_definition;
  }

  function openNodeDialog(gadget, element) {
    var node_id = getNodeId(gadget, element.id),
      node_data = gadget.props.data.graph.node[node_id],
      node_edit_popup = $(gadget.props.element).find('#popup-edit-template'),
      schema,
      fieldset_element,
      delete_promise;
   
    // If we have no definition for this, we do not allow edition.
    if ( gadget.props.data.class_definition[node_data._class] === undefined ) {
      return;
    }

    schema = expandSchema(
      gadget.props.data.class_definition[node_data._class],
      gadget.props.data
    );

    if (node_edit_popup.length !== 0) {
      node_edit_popup.remove();
    }

    gadget.props.element.appendChild(
      document.importNode(popup_edit_template.content, true).children[0]
    );
    node_edit_popup = $(gadget.props.element).find('#node-edit-popup');
    // Set the name of the popup to the node class
    node_edit_popup.find('.node_class').text(node_data._class);
    fieldset_element = node_edit_popup.find('fieldset')[0];
    node_edit_popup.popup();

    node_data.id = node_id; // XXX

    function save_promise(fieldset_gadget, node_id) {
      return RSVP.Queue()
        .push(function () {
          return promiseEventListener(
            node_edit_popup.find("form")[0],
            'submit',
            false
          );
        })
        .push(function (evt) {
          var data = {
              // XXX id should not be handled differently ...
              "id": $(evt.target[1]).val(),
              "data": {}
            };
          return fieldset_gadget.getContent().then(function (r) {
            $.extend(data.data, r);
            updateElementData(gadget, node_id, data);
          });
        });
    }

    delete_promise = new RSVP.Queue()
      .push(function () {
        return promiseEventListener(
          node_edit_popup.find("form [type='button']")[0],
          'click',
          false
        );
      })
      .push(function () {
        return removeElement(gadget, node_id);
      });

    return gadget.declareGadget("../fieldset/index.html", {
      element: fieldset_element,
      scope: 'fieldset'
    })
      .push(function (fieldset_gadget) {
        return RSVP.all([fieldset_gadget,
                         fieldset_gadget.render({value: node_data, 
                                          property_definition: schema},
                                          node_id)]);
      })
      .push(function (fieldset_gadget) {
        node_edit_popup.enhanceWithin();
        node_edit_popup.popup('open');
        return fieldset_gadget[0];
      })
      .push(function (fieldset_gadget) {
        // Expose the dialog handling promise so that we can wait for it in
        // test.
        gadget.props.dialog_promise = RSVP.any([
          // TODO: why different signature ?
          save_promise(fieldset_gadget, node_id),
          delete_promise
        ]);
        return gadget.props.dialog_promise;
      })
      .push(function () {
        node_edit_popup.popup('close');
        node_edit_popup.remove();
        delete gadget.props.dialog_promise;
      });
  }

  function waitForNodeClick(gadget, node) {
    gadget.props.nodes_click_monitor
      .monitor(loopEventListener(
        node,
        'dblclick',
        false,
        openNodeDialog.bind(null, gadget, node)
      ));
  }

  function addNode(gadget, node_id, node_data) {
    var render_element = $(gadget.props.main),
      class_definition = gadget.props.data.class_definition[node_data._class],
      coordinate = node_data.coordinate,
      dom_element_id,
      box,
      absolute_position,
      domElement;

    dom_element_id = generateDomElementId(gadget.props.element);
    gadget.props.node_id_to_dom_element_id[node_id] = dom_element_id;

    node_data.name = node_data.name || class_definition.name;
    gadget.props.data.graph.node[node_id] = node_data;

    if (coordinate === undefined) {
      coordinate = {top: 0, left: 0};
    }

    node_data.coordinate = updateElementCoordinate(
      gadget,
      node_id,
      coordinate
    );

    // XXX make node template an option, or use CSS from class_definition
    /*jslint nomen: true*/
    domElement = domParser.parseFromString(
      node_template({
        "class": node_data._class.replace('.', '-'),
        "element_id": dom_element_id,
        "title": node_data.name || node_data.id,
        "name": node_data.name || node_data.id
      }),
      "text/html"
    ).querySelector('.window');
    render_element.append(domElement);

    waitForNodeClick(gadget, domElement);

    box = $(gadget.props.element).find("#" + dom_element_id);
    absolute_position = convertToAbsolutePosition(
      gadget,
      coordinate.left,
      coordinate.top
    );
    box.css("top", absolute_position[1]);
    box.css("left", absolute_position[0]);
    updateNodeStyle(gadget, dom_element_id);
    draggable(gadget); // XXX make only this element draggable.

    // Add some flowchart endpoints
    // TODO: add them all !
    gadget.props.jsplumb_instance.addEndpoint(dom_element_id, {
        isSource:true,
        maxConnections:-1,
        connector:[ "Flowchart", { stub:[40, 60],
                                   gap:10,
                                   cornerRadius:5,
                                   alwaysRespectStubs:true } ]
        }, { anchor: "BottomCenter",
            uuid: node_id + ".flowchartBottomCenter" });

    gadget.props.jsplumb_instance.addEndpoint(dom_element_id,
        { isTarget:true, maxConnections: -1 },
        { anchor: "LeftMiddle", uuid: node_id + ".flowChartLeftMiddle" });


    gadget.notifyDataChanged();
  }

  function waitForDrop(gadget) {
    var callback;
    function canceller() {
      if (callback !== undefined) {
        gadget.props.main.removeEventListener('drop', callback, false);
      }
    }
    /*jslint unparam: true*/
    function resolver(resolve, reject) {
      callback = function (evt) {
        try {
          var class_name = JSON.parse(
              evt.dataTransfer.getData('application/json')
            ),
            offset = $(gadget.props.main).offset(),
            relative_position = convertToRelativePosition(
              gadget,
              evt.clientX - offset.left + "px",
              evt.clientY - offset.top + "px"
            );
          addNode(gadget,
            generateNodeId(gadget, {_class: class_name}),
            {
              coordinate: {
                left: relative_position[0],
                top: relative_position[1]
              },
              _class: class_name
            });
        } catch (e) {
          reject(e);
        }
      };
      gadget.props.main.addEventListener('drop', callback, false);
    }

    return new RSVP.all( [
      // loopEventListener adds an event listener that will prevent default for
      // dragover
      loopEventListener(gadget.props.main, 'dragover', false,
        function () {return undefined; }),
      RSVP.Promise(resolver, canceller) ]);
  }

  initGadgetMixin(gadget_klass);
  gadget_klass

    .declareAcquiredMethod('notifyDataChanged', 'notifyDataChanged')

    .ready(function (g) {
      g.props.node_id_to_dom_element_id = {};
      g.props.zoom_level = 1.0;
      g.props.style_attr_list = [
        'width',
        'height',
        'padding-top',
        'line-height'
      ];
    })

    .declareMethod('render', function (data) {
      this.props.data = JSON.parse(data);
      this.props.jsplumb_instance = jsPlumb.getInstance();
    })

    .declareMethod('getContent', function () {
      return JSON.stringify(this.props.data);
    })

    .declareMethod('startService', function () {
      var gadget = this;
      this.props.main = this.props.element.querySelector('#main');
      initJsPlumb(this);
      this.props.nodes_click_monitor = RSVP.Monitor();
      $.each(this.props.data.graph.node, function (key, value) {
        addNode(gadget, key, value);
      });
      $.each(this.props.data.graph.edge, function (key, value) {
        addEdge(gadget, key, value);
      });

      return RSVP.all([
        waitForDrop(gadget),
        waitForConnection(gadget),
        waitForConnectionDetached(gadget),
        waitForConnectionClick(gadget),
        gadget.props.nodes_click_monitor
      ]);
    });
}(RSVP, rJS, $, jsPlumb, Handlebars, initGadgetMixin,
  loopEventListener, promiseEventListener, DOMParser));
