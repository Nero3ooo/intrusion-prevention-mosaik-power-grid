# This script automatically generates the borderregion json configs based on the rtu configs

import json
import os


def main():
    print("hello world")
    calculateFromFiles()


# TODO: Entscheiden welche ids verwendet werden. Eventuell eine Liste mit zu erstellenden Border Regions (bzw. deren ids) übergeben.
'''
    input: configs=[{'id':'1', 'config':'<json>'},...]
    output: [{'id_br':'1_2', 'config':'<json>'},...]
'''


def calculateFromJSON(configs=None) -> []:
    if configs is None:
        print("no configs to generate border region from")
        return []

    if len(configs) < 2:
        print("Not enough rtus to generate a border region. At least 2 rtus are required!")

    rtus = []  # rtus (in dicts)
    ids = []  # ids of rtus (as string)
    brs = {}  # border regions (in dicts)

    for c in configs:
        rtus.append(json.loads(c['config']))
        ids.append(c['id'])

    # Find power lines that are included in both RTUs and create border regions named as '<id of rtu0>_<id of rtu1>'
    i = 0
    for rtu0 in rtus:
        j = 0
        for rtu1 in rtus:
            if rtu0 != rtu1 and i < j:
                name = "{}_{}".format(ids[i], ids[j])
                brs[name] = {'power_lines': [], 'switches': [], 'meters': []}

                for l in rtu0['power_lines']:
                    if l in rtu1['power_lines']:
                        brs[name]['power_lines'].append(l)
            j += 1
        i += 1

    # Find other components that are part of the border region
    i = 0
    for rtu0 in rtus:
        j = 0
        for rtu1 in rtus:
            if rtu0 != rtu1 and i < j:
                name = "{}_{}".format(ids[i], ids[j])

                # Get ids of all power_lines in this border region
                pl = []
                for n in brs[name]['power_lines']:
                    pl.append(n['id'])

                # Find switches that are located in this border region
                for s in rtu0['switches']:
                    if s['power_line_id'] in pl and s not in brs[name]['switches']:
                        s['source_id'] = ids[i]
                        brs[name]['switches'].append(s)
                for s in rtu1['switches']:
                    if s['power_line_id'] in pl and s not in brs[name]['switches']:
                        s['source_id'] = ids[j]
                        brs[name]['switches'].append(s)

                # Find meters that are located in this border region
                for m in rtu0['meters']:
                    if m['power_line_id'] in pl and m not in brs[name]['meters']:
                        brs[name]['meters'].append(m)
                for m in rtu1['meters']:
                    if m['power_line_id'] in pl and m not in brs[name]['meters']:
                        brs[name]['meters'].append(m)
            j += 1
        i += 1

    return brs


def calculateFromFiles():
    rtus = []  # rtus (in dicts)
    brs = {}  # border regions (in dicts)

    # Get files of all RTUs
    arr = os.listdir("old-implementation/test_input_files/")
    for f in arr:
        if 'rtu_' in f and '.json' in f:
            # Open RTU files and parse to json and append that to 'rtus' list
            rtu_file = open("old-implementation/test_input_files/" + f, "r")
            rtu = json.load(rtu_file)
            rtu_file.close()
            rtus.append(rtu)
            print("Added an RTU!")

    i = 0
    for rtu0 in rtus:
        j = 0
        for rtu1 in rtus:
            if rtu0 != rtu1 and i < j:
                name = "{}_{}".format(i, j)
                print("Added Border Region: " + name)
                brs[name] = {'power_lines': [], 'switches': [], 'meters': []}

                # Find power lines that are included in both RTUs
                for l in rtu0['power_lines']:
                    if l in rtu1['power_lines']:
                        brs[name]['power_lines'].append(l)
            j += 1
        i += 1

    i = 0
    for rtu0 in rtus:
        j = 0
        for rtu1 in rtus:
            if rtu0 != rtu1 and i < j:
                name = "{}_{}".format(i, j)

                # Get ids of all power_lines in this border region
                pl = []
                for n in brs[name]['power_lines']:
                    pl.append(n['id'])

                # Find switches that are located in this border region
                for s in rtu0['switches']:
                    if s['power_line_id'] in pl and s not in brs[name]['switches']:
                        brs[name]['switches'].append(s)
                for s in rtu1['switches']:
                    if s['power_line_id'] in pl and s not in brs[name]['switches']:
                        brs[name]['switches'].append(s)

                # Find meters that are located in this border region
                for m in rtu0['meters']:
                    if m['power_line_id'] in pl and m not in brs[name]['meters']:
                        brs[name]['meters'].append(m)
                for m in rtu1['meters']:
                    if m['power_line_id'] in pl and m not in brs[name]['meters']:
                        brs[name]['meters'].append(m)
            j += 1
        i += 1

    # Save border regions as separate JSON files
    for b in brs:
        f = open("old-implementation/test_input_files/border_region_" + b + ".json", "w")
        f.write(json.dumps(brs[b], indent=4))
        f.close()


if __name__ == "__main__":
    main()
