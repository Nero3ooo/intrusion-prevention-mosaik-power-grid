import http.server
import socketserver
import json
    
class HttpHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='www', **kwargs)

    def log_message(self, format, *args):
        pass
        
class idvis_webserver:
    def __init__(self):
        self.port = 8080
        print("[WEBVIS] Setting up webserver...")
        with socketserver.TCPServer(("", self.port), HttpHandler) as httpd:
            generator.load_topology(["./data/rtu_0.json", "./data/rtu_1.json"])
            print("[WEBVIS] Server started at localhost:" + str(self.port))
            httpd.serve_forever()

class generator:
    def segment_powerlines(input):
        lines = {}

        # generate segmented powerlines
        for power_line in input:
            line_id = power_line["id"]
            if not line_id in lines:
                lines[line_id] = []

            # join inbound + outbound segments to coherent power_line definition
            if power_line["type"] == "outbound":
                for segment in range(len(power_line["segments"])):
                    lines[line_id].insert(segment, power_line["segments"][segment])
            else:
                for segment in power_line["segments"]:
                    lines[line_id].append(segment)

        # create links
        outline = []
        count = 0
        for line_id in lines:
            segmented = lines[line_id]
            for i in range(len(segmented) - 1):
                outline.append({
                    "id": count,
                    "identifier": line_id + "_" + str(i),
                    "source": segmented[i],
                    "target": segmented[i + 1],
                })
                count += 1

        # pprint(outline)
        return outline

    def load_topology(rtu_files):
        lines = []
        nodes = []
        bus_rtu_lookup = {}

        for rtu in rtu_files:
            rtu_id = rtu.split("_")[1][:-5][::-1]

            with open(rtu) as rtu_json:
                input = json.load(rtu_json)

                lines.extend(input["power_lines"])

                # generate bus nodes
                for bus_ in input['buses']:
                    nodes.append({
                        "id": bus_["id"],
                        "rtu": rtu_id,
                        "type": "bus",
                    })
                    bus_rtu_lookup[bus_["id"]] = rtu_id

                # generate switch nodes
                for switch_ in input["switches"]:
                    nodes.append({
                        "id": switch_["id"],
                        "type": "switch",
                        "rtu": bus_rtu_lookup[switch_["bus_id"]]
                    })

                # generate meter nodes
                for meter_ in input["meters"]:
                    nodes.append({
                        "id": meter_["id"],
                        "type": "meter",
                        "rtu": bus_rtu_lookup[meter_["bus_id"]]
                    })

        links = generator.segment_powerlines(lines)
        out = {
            "rtu_count": len(rtu_files),
            "nodes": nodes,
            "links": links
        }

        with open("www/graph.json", "w") as output_json:
            json.dump(out, output_json, indent=None)

if __name__ == "__main__":
    server = idvis_webserver()