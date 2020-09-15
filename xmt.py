#!/usr/bin/env python3

import csv
import random

with open("in.csv") as input:
    set1 = []
    result = []
    reader = csv.reader(input)
    rowno = 0 
    for row in reader:
        if rowno == 0:
            header = row
        else: 
            set1.append(row)

        rowno = rowno + 1

    f = open("out.csv", "w")
    f.write(",".join(header))
    f.write("\n")

    cache = 1
    cpu = 1
    health = 1
    disks = 1
    for i in range(0, 2314):
        for item in set1:
            item[0]="hst{:05d}:3181".format(i)
            item[2]="hst{:05d}".format(i)
            item[8] = "0"

            if i % 50 == 0 and item[1] == "NT_CACHE":
                item[8] = str(cache)
                cache = cache + 1

            if i % 10 == 0 and item[1] == "NT_CPU":
                item[8] = str(cpu)
                cpu = cpu + 1

            if i % 25 == 0 and item[1] == "NT_HEALTH":
                item[8] = str(health)
                health = health + 1

            if i % 25 == 0 and item[1] == "NT_LOGICAL_DISKS_CONTAINER":
                item[8] = str(disks)
                disks = disks + 1

            f.write(",".join(item))
            f.write("\n")
    f.close()