#-------------------------------------------------------------------------------
# Name:        beach-dune-formatter.py
# Version:     Python 3.9.1, pandas 1.2.0
#
# Purpose:     Processing beach profile data.
#
# Authors:     Ben Chittle, Alex Smith
#-------------------------------------------------------------------------------

import os, re, time
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt


BEN_IN = r"C:\Users\Ben2020\Documents\GitHub\beach-dune-formatter\sample_data"
BEN_OUT = r"C:\Users\Ben2020\Documents\GitHub\beach-dune-formatter\out.xlsx"
UNI_IN = r"E:\SA\Runs\Poly\tables"
UNI_OUT =  r"E:\SA\Runs\Poly\tables\b_poly.xlsx"


####################### PATH SETTINGS #######################
# Change these variables to modify the input and output paths
# (type the path directly using the format above if needed,
# i.e. current_input = r"my\path").
current_input = BEN_IN
current_output = BEN_OUT
#############################################################


def read_mask_csvs(path_to_dir):
    """
    Reads all .csv files in the given directory and concatenates them into a
    single DataFrame. Each .csv file name should end with a number specifying
    the segment its data corresponds to (i.e. 'data_file19.csv' would be
    interpreted to contain data for segment 19).
    """
    # Default value since all testing data is from one state.
    STATE = np.uint8(29)
    INPUT_COLUMNS = ["LINE_ID", "FIRST_DIST", "FIRST_Z"]
    OUTPUT_COLUMNS = ["profile", "x", "y"]
    DTYPES = dict(zip(INPUT_COLUMNS, [np.uint16, np.float32, np.float32]))

    if not path_to_dir.endswith("\\"):
        path_to_dir += "\\"

    # Read each .csv file into a DataFrame and append the DataFrame to a list.
    # The list will be combined into one DataFrame at the end.
    csvs = []
    for file_name in os.listdir(path_to_dir):
        head, extension = os.path.splitext(file_name)
        if extension == ".csv":
            # Look for a segment number at the end of the file name.
            segment = re.search(r"\d+$", head)

            # If a number was found, read the file and append it to the list.
            if segment is not None:
                segment = np.int16(segment.group())

                # Read only the necessary columns (INPUT_COLUMNS) and specify
                # data types for each (saves some memory for large amounts of
                # data).
                csv_data = pd.read_csv(path_to_dir + file_name,
                                       usecols=INPUT_COLUMNS,
                                       dtype=DTYPES)[INPUT_COLUMNS]
                # Rename the columns.
                csv_data.rename(columns=dict(zip(INPUT_COLUMNS, OUTPUT_COLUMNS)),
                                inplace=True)
                # Insert a column for the segment and state values.
                csv_data.insert(loc=0, column="state", value=STATE)
                csv_data.insert(loc=1, column="segment", value=segment)

                csvs.append(csv_data)

                print("\tRead {} rows of data from file '{}'".format(len(csv_data), file_name))
            else:
                print("\tSkipping file '{}' (no segment number found)".format(file_name))
        else:
            print("\tSkipping file '{}' (not a .csv)".format(file_name))

    # Combine the .csvs into a single DataFrame.
    return pd.concat(csvs)


def identify_shore(profile_xy):
    """Returns the x coordinate of the shoreline."""
    # Distance values.
    x = profile_xy["x"]
    # Elevation values.
    y = profile_xy["y"]
    # Slope values.
    slope = (y - y.shift(1)) / (x - x.shift(1))

    # Create a Truth series for filtering the profile by certain conditions.
                # Current y value is greater than 0.
    filtered = ((y > 0)
                # Current y value is the largest so far.
                & (y > y.shift(1).expanding(min_periods=1).max())
                # Current value and next 4 slope values are positive.
                & (slope.rolling(5).min().shift(-4) >= 0))

    # The shore x coordinate is identified at the first position that satisfies
    # the filter.
    x_coord = filtered.idxmax()
    # If no positions satistfied the filter, return no shore.
    if filtered[x_coord]:
        return None
    else:
        return x_coord


def identify_crest(profile_xy, shore_x):
    """Returns the x coordinate of the dune crest."""
    # A subset of the profile data from beyond the identified shore. The crest
    # can only be found within this subset.
    subset = profile_xy.loc[shore_x:]
    # Elevation values.
    y = subset["y"]

    # Create a Truth series for filtering the profile by certain conditions.
            # Current elevation is the largest so far.
    filtered = ((y > y.shift(1).expanding(min_periods=1).max())
                # There is an elevation change of more than 0.6 in the next 20 values.
                & (y - y.rolling(20).min().shift(-20) > 0.6)
                # Current elevation is greater than next 10.
                & (y > y.rolling(10).max().shift(-10)))

    # The crest x coordinate is identified at the first position that satisfies
    # the filter.
    x_coord = filtered.idxmax()
    # If no positions satistfied the filter, return no crest.
    if filtered[x_coord] == False:
        return None
    else:
        return x_coord


def identify_toe(profile_xy, shore_x, crest_x):
    """Returns the x coordinate of the dune toe."""
    # A subset of the profile's data from the identified shore to the 
    # identified crest. The toe can only be found within this subset.
    subset = profile_xy.loc[shore_x:crest_x]
    # Distance values.
    x = subset["x"]
    # Elevation values.
    y = subset["y"]

    # Polynomial coefficients
    A, B, C, D = np.polyfit(x=x, y=y, deg=3)
    # Subtract the elevation values by the polynomial evaluated at the
    # corresponding x coordinate.
    differences = y - ((A * x * x * x) + (B * x * x) + (C * x) + D)
    # The toe x coordinate is identified as the x coordinate corresponding to
    # the minimum value in the above differences series.
    x_coord = differences.idxmin()
    if x_coord == shore_x or x_coord == crest_x:
        return None
    else:
        return x_coord


def identify_heel(profile_df, crest_x):
    """Returns the x coordinate of the dune heel."""
    # A subset of the profile data from beyond the identified crest. The heel
    # can only be found within this subset.
    subset = profile_df.loc[crest_x:]
    # Elevation values
    y = subset["y"]
    # Create a Truth series for filtering the data by some conditions. Note
    # that the "~" symbol inverts the filter i.e. the conditions determine what
    # data to exclude, rather than what data to include as seen previously.
                # There is an elevation change of more than 0.6 in the next 10 values.
    filtered = ~((y - y.rolling(10).min().shift(-10) > 0.6)
                # Current elevation is greater than previous 10.
                & (y > y.rolling(10).max())
                # Current elevation is greater than next 20.
                & (y > y.rolling(20).max().shift(-20)))
    # If no positions satistfied the filter, return no heel.
    if filtered.all():
        return None
    else:
        # Returns the x coordinate of the heel. It is identified at the 
        # position with the minimum y value after filtering the y values.
        return y[filtered].idxmin()


def grouped_mean(profiles, n):
    """Returns a new DataFrame with the mean of every n rows for each column."""
    return profiles.groupby(np.arange(len(profiles)) // n).mean()


def identify_features(profile_xy):
    """
    Returns the coordinates of the shoreline, dune toe, dune crest, and
    dune heel for a given profile as:
    (shore_x, shore_y, toe_x, toe_y, crest_x, crest_y, heel_x, heel_y)
    """
    # Make sure the DataFrame uses the x values as the index. This makes it
    # easy to look up y values corresponding to a given x.
    profile_xy = profile_xy.set_index("x", drop=False)
    # Identify the shore x coordinate if it exists.
    shore_x = identify_shore(profile_xy)
    if shore_x is None:
        print("\tNo shore for {}".format(tuple(profile_xy.iloc[0]["state":"profile"])))
        return None
    
    # Identify the crest x coordinate if it exists.
    crest_x = identify_crest(profile_xy, shore_x)
    if crest_x is None:
        print("\tNo crest for {}".format(tuple(profile_xy.iloc[0]["state":"profile"])))
        return None

    # Identify the toe x coordinate if it exists.
    toe_x = identify_toe(profile_xy, shore_x, crest_x)
    if toe_x is None:
        print("\tNo toe for {}".format(tuple(profile_xy.iloc[0]["state":"profile"])))
        return None

    # Identify the heel x coordinate if it exists.
    heel_x = identify_heel(profile_xy, crest_x)
    if heel_x is None:
        print("\tNo heel for {}".format(tuple(profile_xy.iloc[0]["state":"profile"])))
        return None

    # Retrieve the y values for the above features.
    shore_y, toe_y, crest_y, heel_y = profile_xy.loc[[shore_x, toe_x, crest_x, heel_x], "y"]

    return shore_x, shore_y, toe_x, toe_y, crest_x, crest_y, heel_x, heel_y


def measure_volume(profile_xy, start_x, end_x, profile_spacing, base_elevation=0):
    """
    Returns an approximation of the volume of the beach between two points.

    ARGUMENTS
    profile_xy: DataFrame
      xy data for a particular profile.
    start_x: float
      The x coordinate of the start of the range.
    end_x: float
      The x coordinate of the end of the range.
    profile_spacing: float
      The distance between consecutive profiles.
    base_elevation: float
      Set the height of the horizontal axis to measure volume from. Change this
      if y values are relative to an elevation other than y=0.
    """
    subset = profile_xy.set_index("x", drop=False).loc[start_x:end_x]
    x = subset["x"]
    y = subset["y"]

    # Make all elevation values relative to the base elevation.
    y -= base_elevation

    # The area under the profile curve is calculated using the trapezoidal rule
    # and multiplized by the distance between consecutive profiles to
    # approximate the volume.
    return np.trapz(y=y, x=x) * profile_spacing


### MAKE THIS A HIGHER LEVEL / MULTIPLE PROFILES MODULE FUNCTION AND LEAVE
### measure_volume AS A SINGLE PROFILE FUNCTION

###ASSUMES THAT DATA CAN BE GROUPED BY state, segment, profile.
###RENAME.
def measure_feature_volumes(xy_data, start_values, end_values, base_elevations):
    """
    Returns a list of volumes calculated between the start and end point given
    for each profile.

    ARGUMENTS
    xy_data: DataFrame
      xy data of a collection of profiles.
    start_values: iterable
      Sequence; the x value to start measuring volume from for each profile.
    end_values: iterable
      Sequence; the x value to stop measuring volume from for each profile.
    base_elevations: iterable
      The base elevation for each profile.
    """
    # The distance between consecutive profiles. Uses the distance between the
    # first two consecutive x values, which assumes the profiles were taken from
    # a square grid.
    profile_spacing = xy_data["x"].iat[1] - xy_data["x"].iat[0]

    grouped_xy = xy_data.groupby(["state", "segment", "profile"])
    data = []
    # Measure the volume for each profile between the corresponding start and
    # end x value in start_values and end_values.
    for (index, profile_xy), start_x, end_x, base_y in zip(grouped_xy, start_values, end_values, base_elevations):
        data.append(measure_volume(profile_xy, start_x, end_x, profile_spacing, base_y))

    return data


def write_data_excel(path_to_file, dataframes, names):
    """
    Write data to an Excel file.

    ARGUMENTS
    path_to_file: string
    dataframes: iterable
      Sequence of DataFrames to write. Each element is written on a new sheet.
    names: iterable
      The name of each sheet, corresponding to each element in 'dataframes'.
    """
    with pd.ExcelWriter(path_to_file) as writer:
        for name, data in zip(names, dataframes):
            try:
                data.to_excel(writer, name)
            except IndexError:
                print("\tFailed to write {} to file (the DataFrame may be"
                      " empty).".format(name))



### HAVE THE USER DECLARE HOW THEIR DATA IS CATEGORIZED / ORGANIZED
### (need to know for groupby operations)
def main(input_path, output_path):
    FEATURE_COLUMNS = ["shore_x",  "shore_y", "toe_x", "toe_y", "crest_x",
                       "crest_y", "heel_x", "heel_y"]

    pd.options.display.max_columns = 12
    pd.options.display.width = 100

    initial_start_time = time.perf_counter()

    print("\nReading .csv's...")
    start_time = time.perf_counter()
    xy_data = read_mask_csvs(input_path)
    print("\tTook {:.2f} seconds".format(time.perf_counter() - start_time))


    print("\nIdentifying features...")
    start_time = time.perf_counter()

    # Identify the shoreline, dune toe, dune crest, and dune heel for each
    # profile in the data. This data will be returned as a Pandas Series
    # containing tuples of the 4 pairs of coordinates for each profile.
    profiles = xy_data.groupby(["state", "segment", "profile"]).apply(identify_features)

    # Expand the Series of tuples into a DataFrame where each column contains an
    # x or y componenent of a feature.
    profiles = pd.DataFrame(profiles.to_list(), columns=FEATURE_COLUMNS, index=profiles.index)
    print("\tTook {:.2f} seconds".format(time.perf_counter() - start_time))


    print("\nCalculating beach data...")
    start_time = time.perf_counter()

    # Use the feature data for each profile to calculate additional
    # characteristics of the beach. This includes the dune height, beach width,
    # dune toe height, dune crest height, dune length, beach slope, dune slope,
    # beach volume, dune volume, and beach-dune volume ratio.
    beach_data = pd.DataFrame(
        data={"dune_height" : profiles["crest_y"] - profiles["toe_y"],
              "beach_width" : profiles["toe_x"] - profiles["shore_x"],
              "dune_toe" : profiles["toe_y"],
              "dune_crest" : profiles["crest_y"],
              "dune_length" : profiles["crest_x"] - profiles["toe_x"]},
        index=profiles.index)

    # Approximates the beach slope as the total change in height of the beach
    # divided by the length of the beach.
    beach_data["beach_slope"] = (profiles["toe_y"] - profiles["shore_y"]) / beach_data["beach_width"]

    # Approximates the dune slope as the change in height of the dune divided by
    # the length of the dune.
    beach_data["dune_slope"] = beach_data["dune_height"] / beach_data["dune_length"]

    beach_data["beach_vol"] = measure_feature_volumes(
                                  xy_data,
                                  start_values=profiles["shore_x"],
                                  end_values=profiles["toe_x"],
                                  base_elevations=profiles["shore_y"])
    ### ARE ELEVATIONS RELATIVE TO TOE Y OR SHORE Y?
    beach_data["dune_vol"] = measure_feature_volumes(
                                 xy_data,
                                 start_values=profiles["toe_x"],
                                 end_values=profiles["crest_x"],
                                 base_elevations=profiles["toe_y"])
    ### SHOULD THIS BE db_ratio?
    beach_data["bd_ratio"] = beach_data["dune_vol"] / beach_data["beach_vol"]
    print("\tTook {:.2f} seconds".format(time.perf_counter() - start_time))


    print("\nFiltering data...")
    start_time = time.perf_counter()

    ### SHOULD THE ENTIRE ROW OF DATA BE WIPED OUT IF ONLY ONE FEATURE IS UNFIT?
    filtered_beach_data = beach_data[
          (beach_data["dune_vol"] < 300) ##
        & (beach_data["beach_vol"] < 500) ##
        & (beach_data["dune_height"] > 1)
        & (beach_data["dune_height"] < 10)
        & (beach_data["dune_length"] > 5)
        & (beach_data["dune_length"] < 25)
        & (beach_data["dune_crest"] < 20)
        & (beach_data["beach_width"] > 10)
        & (beach_data["beach_width"] < 60)].dropna()
    print("\tTook {:.2f} seconds".format(time.perf_counter() - start_time))
    print("\tThere are {} profiles remaining after filtering out {} rows of"
          " data.".format(len(filtered_beach_data), len(beach_data) - len(filtered_beach_data)))


    print("\nAveraging data...")
    start_time = time.perf_counter()

    # Takes the mean of each column for every 10 profiles.
    averaged_beach_data = beach_data.groupby(["state", "segment"]).apply(grouped_mean, 10)
    print("\tTook {:.2f} seconds".format(time.perf_counter() - start_time))


    print("\nCorrelating data...")
    start_time = time.perf_counter()
    corr1 = beach_data.corr(method="pearson")
    corr2 = filtered_beach_data.corr(method="pearson")
    print("\tTook {:.2f} seconds".format(time.perf_counter() - start_time))


    print("\nWriting to file...")
    start_time = time.perf_counter()
    write_data_excel(path_to_file=output_path,
                     dataframes=(profiles, beach_data, corr1, filtered_beach_data,
                                 corr2, averaged_beach_data),
                     names=("profiles", "unfiltered", "corr_1", "filtered",
                            "corr_2", "averages"))
    print("\tTook {:.2f} seconds".format(time.perf_counter() - start_time))

    print("\nTotal time: {:.2f} seconds".format(time.perf_counter() - initial_start_time))

    #return xy_data, profiles, beach_data, filtered_beach_data, averaged_beach_data


if __name__ == "__main__":
    #xy_data, profiles, beach_data, filtered_beach_data, avg = main(current_input, current_output)
    main(current_input, current_output)

