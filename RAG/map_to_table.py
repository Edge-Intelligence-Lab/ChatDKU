import csv

building_data = [
    ["Academic Building / AB", "Center North", "Faculty Residence Courtyard", "Innovation Building / IB", "Conference Center / CC", "WHU-DUKE Research Institute"],
    ["Innovation Building / IB", "Center South", "Academic Building / AB", "Graduate Student Center", "Conference Center / CC", "Library / LIB"],
    ["WHU-DUKE Research Institute / WDR", "Center North", "", "Academic Building / AB", "Library / LIB", "Wuhan University Road"],
    ["Library / LIB", "Center South", "Innovation Building / IB", "Visitor Center / VCT", "Community Center / CCT", "WHU-DUKE Research Institute"],
    ["Conference Center / CC", "Center", "Academic Building / AB", "", "Wuhan University Road", "Innovation Building / IB"],
    ["Graduate Student Center", "East Center", "", "Faculty Residence Courtyard", "Employee Center Courtyard", "Innovation Building / IB"],
    ["Faculty Residence Courtyard", "North Center", "", "Graduate Student Center", "", "Academic Building / AB"],
    ["Residence Hall", "Center North West", "", "", "Campus Lounge", "Wuhan University Road"],
    ["Employee Center Courtyard", "East", "", "", "Tennis Court (S)", "Graduate Student Center"],
    ["Sports Complex / SPC", "South", "", "Soccer Field", "", "Wuhan University Road"],
    ["Soccer Field", "South", "Sports Complex / SPC", "Basketball Court", "", "Wuhan University Road"],
    ["Basketball Court", "South", "Soccer Field", "", "Tennis Court (N)", ""],
    ["Tennis Court (N)", "South", "", "", "", "Basketball Court"],
    ["Tennis Court (S)", "South", "", "", "", "Basketball Court"],
    ["Campus Lounge", "North", "", "Residence Hall", "", "Residence Hall"],
    ["Visitor Center / VCT", "Center", "", "Community Center / CCT", "", "Library / LIB"],
    ["Community Center / CCT", "South", "Visitor Center / VCT", "", "", "Wuhan University Road"]
]


non_building_data = [
    ["Public Parking Lot", "Residence Hall", "South"],
    ["Underground Parking (Public)", "Residence Hall", "South"],
    ["Underground Parking (DKU Members)", "Residence Hall", "South"],
    ["Shuttle Bus Stop", "Innovation Building / IB", "South"],
    ["Bicycle Parking", "Sports Complex / SPC", "East"],
    ["Electric Bike Charging Station", "Community Center / CCT", "South"],
    ["Ambulance Parking", "Library / LIB", "North"],
    ["Emergency Assembly Area", "Library / LIB", "South"],
    ["Smoking Area", "Innovation Building / IB", "North"]
]


building_file = "duke_kunshan_university_buildings.csv"
non_building_file = "duke_kunshan_university_locations.csv"


with open(building_file, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Building Name", "Relative Location", "North", "South", "East", "West"])
    writer.writerows(building_data)


with open(non_building_file, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Location Name", "Nearest Building", "Relative Direction"])
    writer.writerows(non_building_data)

print(f"Building data has been written to {building_file}")
print(f"Location data has been written to {non_building_file}")
