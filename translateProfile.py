# usage: python translateProfile.py <absolute paths to all Argo netcdf files relevant for this profile>
# populates mongodb argo/argo and argo/argoMeta with the contents of the provided file(s)
# assumes https://github.com/argovis/db-schema/blob/main/argo.py was run first to create the collection with schema enforcement and indexing
# assumes rsync populated content under /ifremer, same as choosefiles.py

import sys, xarray, re, datetime, difflib, pprint, numpy
from pymongo import MongoClient
import util.helpers as h

client = MongoClient('mongodb://database/argo')
db = client.argo

print('parsing', sys.argv[1:])

# extract and merge data, data_keys, units and data_keys_mode
separate_data = [h.extract_data(x) for x in sys.argv[1:]]
data = h.merge_data(separate_data)

# extract and merge everything else, and check for consistency between files
separate_metadata = [h.extract_metadata(x) for x in sys.argv[1:]]
if not h.compare_metadata(separate_metadata):
	print('error: files', sys.argv[1:], 'did not yield consistent metadata')
metadata = h.merge_metadata(separate_metadata)

# construct metadata record for the argoMeta table
argoMeta = {}
metaCopy = ['data_type', 'country', 'data_center', 'instrument', 'pi_name', 'platform', 'platform_type', 'fleetmonitoring', 'oceanops', 'positioning_system', 'wmo_inst_type']
for key in metaCopy:
	if key in metadata:
		argoMeta[key] = metadata[key]

# construct data record for the argo table
argo = {}
dataCopy = ['_id', 'geolocation', 'basin', 'timestamp', 'date_updated_argovis', 'source', 'data_warning', 'cycle_number', 'geolocation_argoqc', 'profile_direction', 'timestamp_argoqc', 'vertical_sampling_scheme']
for key in dataCopy:
	if key in metadata:
		argo[key] = metadata[key]
argo['data'] = data['data']
argo['data_keys_mode'] = data['data_keys_mode']
## append data warnings to argo["data_warnings"] object
if "degenerate_levels" in data["data_annotation"] and data["data_annotation"]["degenerate_levels"]:
	if "data_warning" not in argo:
		argo["data_warning"] = []
	if "degenerate_levels" not in argo["data_warning"]:
		argo["data_warning"].append("degenerate_levels")

# determine if this is a BGC profile, and assign data_keya and units accordingly
sources = [item for sublist in [x['source'] for x in argo['source']] for item in sublist]
if 'argo_bgc' in sources:
	argo['data_keys'] = data['data_keys']
	argo['units'] = data['units']
else:
	argoMeta['data_keys'] = data['data_keys']
	argoMeta['units'] = data['units']

# determine if an appropriate pre-existing metadata record exists, and upsert metadata if required
try:
    platformmeta = list(db.argoMeta.find({"platform": argoMeta['platform'] }))
    argoMeta['_id'] = h.determine_metaid(argoMeta, platformmeta, str(argoMeta['platform']) + "_m")
    print(argoMeta)
    #db.argoMeta.replace_one({'_id': argoMeta['_id']}, argoMeta, True)
except BaseException as err:
    print('error: metadata upsert failure on', argoMeta)
    print(err)

argo['metadata'] = argoMeta['_id']
# write data record to mongo
try:
    #db.argo.insert_one(argo)
    print(argo)
except BaseException as err:
    print('error: db write failure')
    print(err)
    print(argo)




# look for mandatory and optional keys, complain appropriately

# # extract metadata for each file and make sure it's consistent between all files being merged
# separate_metadata = [h.extract_metadata(x) for x in sys.argv[1:]]
# if not h.compare_metadata(separate_metadata):
# 	print('error: files', sys.argv[1:], 'did not yield consistent metadata')

# # merge metadata into single object
# metadata = h.merge_metadata(separate_metadata)

# print(metadata)

# # extract data variables for each file separately
# separate_data = [h.extract_data(x) for x in sys.argv[1:]]

# # merge data into single pressure axis list
# data = h.merge_data(separate_data)
# ## append data warnings to metadata["data_warnings"] object
# if "degenerate_levels" in data["data_annotation"] and data["data_annotation"]["degenerate_levels"]:
# 	if "data_warning" not in metadata:
# 		metadata["data_warning"] = []
# 	if "degenerate_levels" not in metadata["data_warning"]:
# 		metadata["data_warning"].append("degenerate_levels")
# del data["data_annotation"]

# combine metadata + data and return
#profile = {**metadata, **data}

# # write to mongo
# try:
# 	db.profiles.replace_one({"_id": profile['_id']}, profile, upsert=True)
# except BaseException as err:
# 	print('error: db write failure')
# 	print(err)
# 	print(profile)