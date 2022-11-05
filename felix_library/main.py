def main(currency_pairs):
    """
    The Function run to data engineering code by MAX

    :param currency_pairs: A list contain portfolio info
    :type currency_pairs: list
    """

    # The api key given by the professor
    key = "beBybSi8daPgsTp5yx5cHtHpYcrjp5Jq"
    
    # Number of list iterations - each one should last about 1 second
    count = 0
    agg_count = 0
    
    # Create an engine to connect to the database; setting echo to false should stop it from logging in std.out
    engine = create_engine("sqlite+pysqlite:///sqlite/final.db", echo=False, future=True)
    
    # Create the needed tables in the database
    initialize_raw_data_tables(engine,currency_pairs)
    initialize_aggregated_tables(engine,currency_pairs)
    
    # Open a RESTClient for making the api calls
    with RESTClient(key) as client:
        # Loop that runs until the total duration of the program hits 24 hours. 
        while count < 86400: # 86400 seconds = 24 hours
            
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
                    resp = client.forex_currencies_real_time_currency_conversion(from_, to, amount=100, precision=2)
                except:
                    continue

                # This gets the Last Trade object defined in the API Resource
                last_trade = resp.last

                # Format the timestamp from the result
                dt = ts_to_datetime(last_trade["timestamp"])

                # Get the current time and format it
                insert_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Calculate the price by taking the average of the bid and ask prices
                avg_price = (last_trade['bid'] + last_trade['ask'])/2

                # Write the data to the SQLite database, raw data tables
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO "+from_+to+"_raw(ticktime, fxrate, inserttime) VALUES (:ticktime, :fxrate, :inserttime)"),[{"ticktime": dt, "fxrate": avg_price, "inserttime": insert_time}])