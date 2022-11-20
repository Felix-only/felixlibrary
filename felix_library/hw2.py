# Import required libraries
import datetime
import time
from polygon import RESTClient
from sqlalchemy import create_engine 
from sqlalchemy import text
from math import sqrt
from math import isnan
import matplotlib.pyplot as plt
from numpy import mean
from numpy import std
from math import floor
import numpy as np
import pandas as pd

def keltner_channel(currency_pairs):
    """
    The Function run to data engineering code by MAX

    :param currency_pairs: A list contain portfolio info
    :type currency_pairs: list
    """
    ########################################################
    #this is the function that main needed:
    # write a function to dml the keltner channel column
    
    # write a function to clean the outlier of in the raw data values. 
    def clean_outlier(pd_series):
        '''
        Input a pandas series, output a cleaned pandas series
        '''
        Q1 = pd_series.quantile(0.25)
        Q3 = pd_series.quantile(0.75)
        IQR = Q3 - Q1
        
        minimum_val = Q1 - 1.5*IQR
        maximum_val = Q3 + 1.5*IQR
        output = pd_series[(pd_series >= minimum_val) & (pd_series <= maximum_val)]
        
        return output

    # count how many item in a list, for counting N for the fd
    def count_range_in_list(li, min_, max_):
        count = 0
        for i in li:
            if (i >= min_) and (i <= max_):
                count += 1
        return count

    # Function slightly modified from polygon sample code to format the date string 
    def ts_to_datetime(ts) -> str:
        return datetime.datetime.fromtimestamp(ts / 1000.0).strftime('%Y-%m-%d %H:%M:%S')

    # Function which clears the raw data tables once we have aggregated the data in a 6 minute interval
    def reset_raw_data_tables(engine,currency_pairs):
        with engine.begin() as conn:
            for curr in currency_pairs:
                conn.execute(text("DROP TABLE "+curr[0]+curr[1]+"_raw;"))
                conn.execute(text("CREATE TABLE "+curr[0]+curr[1]+"_raw(ticktime text, fxrate  numeric, inserttime text);"))

    # This creates a table for storing the raw, unaggregated price data for each currency pair in the SQLite database
    def initialize_raw_data_tables(engine,currency_pairs):
        with engine.begin() as conn:
            for curr in currency_pairs:
                conn.execute(text("CREATE TABLE "+curr[0]+curr[1]+"_raw(ticktime text, fxrate  numeric, inserttime text);"))

    # This creates a table for storing the (6 min interval) aggregated price data for each currency pair in the SQLite database            
    def initialize_aggregated_tables(engine,currency_pairs):
        with engine.begin() as conn:
            for curr in currency_pairs:
                conn.execute(text("CREATE TABLE "+curr[0]+curr[1]+
                                '''_agg(avgfxrate  numeric, minfxrate numeric, 
                                    maxfxrate numeric, vol numeric, fd numeric); ''' ))

    # This function is called every 6 minutes to aggregate the data, store it in the aggregate table, 
    # and then delete the raw data
    def aggregate_raw_data_tables(engine,currency_pairs):
        with engine.begin() as conn:
            for curr in currency_pairs:
                
                #get the fxrate in our raw data for fd calculation 
                fxrate_res = conn.execute(text("SELECT fxrate FROM "+curr[0]+curr[1]+"_raw;"))
                fxrate_data = [row.fxrate for row in fxrate_res]
                # use pandas to clean the data
                fxrate_series = pd.Series(fxrate_data)
                clean_fxrate =clean_outlier(fxrate_series)
                # calcuate avg, count, min, max , and vol in the clean data.
                avg_price = clean_fxrate.mean()
                tot_count = clean_fxrate.count()
                min_price = clean_fxrate.min()
                max_price = clean_fxrate.max()
                vol = max_price - min_price
                
                # add keltner channel (KCUB and KCLB) into our table, put name and values in the dictionary
                kcub_values = []
                kclb_values = []
                for i in range(100):
                    kcub_values.append(avg_price + (i+1)*0.025*vol)
                    kclb_values.append(avg_price - (i+1)*0.025*vol)
                
                # after calculation make to series to list.  
                fxrate_data = clean_fxrate.to_list()
                # then we will slice the data into increasing range
                increase_bound = np.split(fxrate_data, np.where(np.diff(fxrate_data) < 0)[0]+1)
                increase_revert_bound = [(increase_bound[i][0], increase_bound[i-1][-1]) for i in range(1, len(increase_bound))]
                
                
                # get FD values
                # first make copy of the list
                kcub_values_copy = kcub_values.copy()
                kclb_values_copy = kclb_values.copy()
                kcub_values_copy.extend(kclb_values_copy)
                keltner_values = kcub_values_copy.copy()
                
                if not curr[2]:
                    fd = None
                    curr[2].append(keltner_values)
                else:
                    if vol == 0:
                        fd = 0
                        curr[2].append(keltner_values)
                    else:
                        # get the N for fd which is keltner_tot_count
                        N_count = 0
                        for i in increase_bound:
                            N_count += count_range_in_list(curr[2][-1], i[0], i[-1])
                        for i in increase_revert_bound:
                            N_count += count_range_in_list(curr[2][-1], i[0], i[-1])
                        # after we calculate N_count, we can calculate fd by dividing the vol
                        fd = N_count / vol
                        curr[2].append(keltner_values)
                
                #insert the values into the agg tables
                conn.execute(text("INSERT INTO "+curr[0]+curr[1]+
                                '''_agg VALUES (:avgfxrate, :minfxrate, :maxfxrate, :vol, :fd);'''),
                            {'avgfxrate': avg_price, 'minfxrate': min_price,  'maxfxrate': max_price, 'vol': vol, 'fd': fd})
                
                
            

    ########################################################

    # The api key given by the professor
    key = "beBybSi8daPgsTp5yx5cHtHpYcrjp5Jq"
    
    # Number of list iterations - each one should last about 1 second
    count = 0
    agg_count = 0
    
    # Create an engine to connect to the database; setting echo to false should stop it from logging in std.out
    engine = create_engine("sqlite+pysqlite:///sqlite/final_v5_fd_updated.db", echo=False, future=True)
    
    # Create the needed tables in the database
    initialize_raw_data_tables(engine,currency_pairs)
    initialize_aggregated_tables(engine,currency_pairs)
    
    # Open a RESTClient for making the api calls
    client = RESTClient(key)
    # Loop that runs until the total duration of the program hits 24 (10) hours. 
    while count <= 36000: # 86400 seconds = 24 hours || 36000 seconds = 10 hours 
        # Make a check to see if 6 minutes has been reached or not
        if agg_count == 360:
            # Aggregate the data and clear the raw data tables
            aggregate_raw_data_tables(engine,currency_pairs)
            reset_raw_data_tables(engine,currency_pairs)
            agg_count = 0

        # Only call the api every 1 second, so wait here for 0.75 seconds, because the 
        # code takes about .15 seconds to run
        time.sleep(0.75)

        # Increment the counters
        count += 1
        agg_count +=1

        # Loop through each currency pair
        for currency in currency_pairs:
            # Set the input variables to the API
            from_ = currency[0]
            to = currency[1]

            # Call the API with the required parameters
            try:
                resp = client.get_real_time_currency_conversion(from_, to, amount=100, precision=2)
            except:
                continue

            # This gets the Last Trade object defined in the API Resource
            last_trade = resp.last

            # Format the timestamp from the result
            dt = ts_to_datetime(last_trade.timestamp)

            # Get the current time and format it
            insert_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Calculate the price by taking the average of the bid and ask prices
            avg_price = (last_trade.bid + last_trade.ask)/2

            # Write the data to the SQLite database, raw data tables
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO "+from_+to+"_raw(ticktime, fxrate, inserttime) VALUES (:ticktime, :fxrate, :inserttime)"),[{"ticktime": dt, "fxrate": avg_price, "inserttime": insert_time}])