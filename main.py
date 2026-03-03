import requests
import argparse
import json
from great_tables import GT
import copy
import pandas as pd
import plotly.graph_objects as go

# this creates an array with factionIDs where the unit is present and 0s where it's not
def createFactionMask(unitFactions, factionIDsAll):

    data = copy.deepcopy(factionIDsAll)

    for i in range(len(data)):

        if data[i] not in unitFactions:

            data[i] = 0

    return data

# construct a binary number ID that represents the set/mask
def createSetID(factionMask):

    counter = len(factionMask)-1

    sum = 0

    for val in factionMask:

        if val > 0 :

            sum += 2**counter

        counter-=1

    return sum

# creates a dict of binaryID->index
# this will be used to quickly/easily select the appopriate column to add a unit name to
def createIntersectionColumnGuide(sets):

    columnGuide = {}

    for i in range(len(sets)):

        setID = createSetID(sets[i])

        columnGuide[setID] = i

    return columnGuide

def stripLogoURL(url):

    tokens = url.split('/')

    return tokens[-1]


def selectFactions():

    armyMetadata = requests.get("https://api.corvusbelli.com/army/infinity/en/metadata",
                                headers={'Origin': 'https://infinityuniverse.com/'}).text

    armyMetaJson = json.loads(armyMetadata)

    factions = armyMetaJson["factions"]

    factionIDs = []

    factionNameIDdict = {}

    for faction in factions:
        ID = faction["id"]

        factionIDs.append(faction["id"])

        nameStr = faction["name"]

        if len(nameStr) > 20 and len(faction["slug"]) < len(nameStr):
            nameStr = faction["slug"]

        factionNameIDdict[ID] = nameStr

        print(str(ID) + " : " + nameStr)

    choices = input("Choose factions (use , delimiters):")

    choices = choices.split(',')
    validatedChoices = []

    croppedFactionNameDict = {}

    for val in choices:

        if val.isdigit() and int(val) in factionNameIDdict:

            validatedChoices.append(int(val))
            croppedFactionNameDict[int(val)]=factionNameIDdict[int(val)]

        else:
            print("Choice " + val + " is invalid")



    return (validatedChoices,croppedFactionNameDict)

# creates a list of all unique intersections
def identifySets(unitData):

    subsets = []

    for unit in unitData.values():

        if unit["mask"] not in subsets:

            subsets.append(unit["mask"])

    return subsets

# creates the strings used for each intersection
def createIntersectionLabels(sets, factionNameDict):

    labels = [""] * len(sets)

    for i in range(len(sets)):

        labelStrs = []

        for factionID in sets[i]:

            if factionID > 0:

                labelStrs.append(factionNameDict[factionID])

        label = ""

        if len(labelStrs) == len(factionNameDict):

            label = "Common"

        else:

            label = ','.join(labelStrs)

        labels[i] = label

    return labels

# make a dict of all units in all sets
def prepUnitData(factionIDs):

    unitData = {}

    for factionID in factionIDs:

        url = "https://api.corvusbelli.com/army/units/en/" + str(factionID)

        factionData = requests.get(url, headers={'Origin': 'https://infinityuniverse.com/'}).text

        factionJson = json.loads(factionData)

        units = factionJson["units"]

        for unit in units:

            unitName = ""

            if unit["id"] > 10000:
                continue

            if unit["iscAbbr"]:

               unitName = unit["iscAbbr"]

            else:

                unitName = unit["isc"]

            if unitName in unitData:
                continue
            else:

                newUnitEntry = {}

                factionBits = createFactionMask(unit["factions"], factionIDs)

                logo = stripLogoURL(unit["profileGroups"][0]["profiles"][0]["logo"])

                newUnitEntry["mask"] = factionBits

                newUnitEntry["logo"] = logo

                unitData[unitName] = newUnitEntry

    return unitData


def createIntersectionDataFrame(unitData, labels, columnGuide):

    dict = {}

    # add a column for each set
    for label in labels:

        dict[label]=[]

    # add units to appropriate columns

    for unitName, unitData in unitData.items():

        setID = createSetID(unitData["mask"])

        columnID = columnGuide[setID]

        columnSelection = labels[columnID]

        dict[columnSelection].append(unitName)

    # pad columns

    maxLen = 0

    for column in dict.values():

        maxLen = max(maxLen, len(column))

    for column in dict.values():

        column.sort()

        while len(column) < maxLen:

            column.append("")

    return pd.DataFrame(data=dict)

def createTitle(factionNameDict):

    words = []

    for str in factionNameDict.values():

        words.append(str)

    return "Unit Overlap: " + ",".join(words)


def transformFactionMask(factionMask, factionNameDict):

    factionStrs = {}

    for faction in factionMask:

        if faction > 0:

            str = factionNameDict[faction]

            factionStrs[str] = True

    return factionStrs

def createGridDataFrame(unitData, factionNameDict):

    labels = []

    for factionStr in factionNameDict.values():

        labels.append(factionStr)

    dict = {"Unit" : []}

    for label in labels:

        dict[label] = []

    for unitName, unitValues in unitData.items():

        dict["Unit"].append(unitName)

        unitFactions = unitValues["mask"]

        unitFactionsStr = transformFactionMask(unitFactions, factionNameDict)

        for label in labels:

            if label in unitFactionsStr:
                dict[label].append("x")
            else:
                dict[label].append("")

    return (pd.DataFrame(data=dict), labels)



def columnIntersectionsView(factionNameDict, unitData):

    sets = identifySets(unitData)

    labels = createIntersectionLabels(sets, factionNameDict)

    title = createTitle(factionNameDict)

    columnGuide = createIntersectionColumnGuide(sets)

    df = createIntersectionDataFrame(unitData, labels, columnGuide)

    table = GT(df).tab_header(title).tab_options(table_body_vlines_style="solid")

    table.save("Intersection " + title + ".png")

def gridView(factionNameDict, unitData):


    title = createTitle(factionNameDict)

    df, labels = createGridDataFrame(unitData, factionNameDict)

    table = GT(df).tab_header(title).tab_options(table_body_vlines_style="solid")

    table.save("Grid " + title + ".png")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog="Infinity Unit Overlap", description="Download Infinity Army Data, calculate overlaps and print vizualization")

    parser.add_argument('-I', help="Show set intersections", action='store_true')

    parser.add_argument('-G', help="Show unit grid", action='store_true')

    args = parser.parse_args()

    # prompt for console input to select factions for comparison, also get an easy dict for faction-factionName translation
    # this involves a request to CB api for unit data
    (factionIDs, factionNameDict) = selectFactions()

    # download data for each faction
    # each unit stores only its name and faction it's in
    unitData = prepUnitData(factionIDs)

    if args.I:

        columnIntersectionsView(factionNameDict, unitData)
        print("Column View written")

    if args.G:

        gridView(factionNameDict, unitData)
        print("Grid View written")