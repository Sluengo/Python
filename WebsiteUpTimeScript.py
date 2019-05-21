import requests
import os
import time
import hashlib
import base64
import hmac
import json
import datetime
import boto3
import pandas as pd

# Account Info for Logic Monitor. Add your access Key Here.
AccessId = ""
AccessKey = ""
Company = "puppyspot"

# Set Root Directory for Data. Change this if moving to another Server.
RootDir = 'C:\Users\SLuengo\PycharmProjects\LogicMonitor'

# Setting up Dictionary Objects of each website
puppyspot_main = {'service': 'puppyspot.com','ID': 1, 'overall_status': 5,'DC':4, 'SF': 23789978}
about_us = {'service': 'puppyspot-about-us', 'ID' : 72, 'overall_status': 247912111, 'DC': 247912110, 'SF': 247912112}
content = {'service': 'puppyspot-content', 'ID' : 31, 'overall_status': 23648641, 'DC': 23648640, 'SF': 23648655}
for_sale = {'service': 'puppyspot-for-sale', 'ID' : 74, 'overall_status': 330603119, 'DC': 330603118, 'SF': 330603120}
leadtacker = {'service': 'leadtracker', 'ID' : 67, 'overall_status': 181661087, 'DC': 181661086, 'SF': 181661088}

# Create dictionary array of each website
websites = [puppyspot_main, about_us, content, for_sale, leadtacker]

# This function returns the timestamps needed to make the API calls
def GetTime():
    print("Setting up time conditions for API queries...")
    now = datetime.datetime.now()
    date = now.strftime("%m-%d-%Y")

    today = time.time()
    today = int(today)
    week_ago = today - 604800
    three_hours = week_ago + 10800

    timestamps = {
        'start_time': week_ago,
        'three_hours': three_hours,
        'while_end': today,
        'date': date
    }
    return timestamps

# This function compiles the data collected from GetData
# CompileData(compileDataRootDir, resource_path['name'], datapoint, website['service'], timestamps['date'])
def CompileData(compileDataRootDir, location, status_name, service_name, date):
    print("Compiling API calls into single dataframe...")
    new_times = []
    new_statuses = []

    # This should be the name of the site
    service_names = []

    # this should be DC or SF or Overall
    locations = []

    df = pd.DataFrame()

    # Cd to that directory
    os.chdir(compileDataRootDir)

    # get the substring for location. Getting overall, DC, or SF.
    location = location.split('_')
    location = location[0]

    for file in os.listdir(compileDataRootDir):
          with open(file) as f:
                object = json.load(f)
                statuses = object['data']['values']
                times = object['data']['time']
                for time in times:
                      # converts Long data type into datetime
                      converted = datetime.datetime.fromtimestamp(time/1000.0).strftime('%Y-%m-%d %H:%M:%S')
                      new_times.append(converted)
                for status in statuses:
                      # The list of statuses is each an individual list. So, I did this to get a "float" type and append the float to a new list
                      new_statuses.append(status[0])
                      locations.append(location)
                      service_names.append(service_name)

    # Convert the arrays into dataframe objects
    df['Time'] = new_times
    df[status_name] = new_statuses
    df['Service'] = service_names
    df['Location'] = locations

    file_name = date + '-' + service_name + '-' +  location + '.csv'
    df.to_csv(file_name, index=False)

    UploadToS3(compileDataRootDir,file_name,location)

# This function gets the data
def GetData(websites,timestamps, AccessId, AccessKey, Company):
    print('Gathering Data from LogicMonitor...')
    for website in websites:
        print(website)
        # Setup resource paths
        overall_status = {'path':'/service/services/' + str(website['ID']) + '/checkpoints/' + str(website['overall_status']) + '/data', 'name': 'overall_status'}
        dc_response_time = {'path':'/service/services/'+ str(website['ID']) +'/checkpoints/' + str(website['DC']) + '/data', 'name': 'dc_response_time'}
        sf_response_time = {'path':'/service/services/'+ str(website['ID']) +'/checkpoints/' + str(website['SF']) + '/data', 'name': 'sf_response_time'}

        resource_paths = [overall_status, dc_response_time, sf_response_time]

        #setup incrementor
        number = 1

        for resource_path in resource_paths:
            # Start time
            start_date = timestamps['start_time']
            # Three hours later - Can only grab three hours of data at a time
            three_hours = timestamps['three_hours']
            # This is to set the full length of the loop, how far in time you want to go
            while_end = timestamps['while_end']

            os.chdir(RootDir +'\/' + website['service'] + '\/' + resource_path['name'])

            while three_hours < while_end:

                    # Set Datapoint
                    if resource_path['name'] == 'overall_status':
                        datapoint = 'overallStatus'
                    else:
                        datapoint = 'responseTime'

                    #Request Info
                    httpVerb ='GET'
                    resourcePath = resource_path['path']
                    payload = {'datapoints': datapoint,'start': start_date,'end': three_hours }
                    data = ''

                    #Construct URL
                    url = 'https://'+ Company +'.logicmonitor.com/santaba/rest' + resourcePath

                    #Get current time in milliseconds
                    epoch = str(int(time.time() * 1000))

                    #Concatenate Request details
                    requestVars = httpVerb + epoch + resourcePath

                    #Construct signature
                    signature = base64.b64encode(hmac.new(AccessKey,msg=requestVars,digestmod=hashlib.sha256).hexdigest())

                    #Construct headers
                    auth = 'LMv1 ' + AccessId + ':' + signature + ':' + epoch
                    headers = {'Content-Type':'application/json','Authorization':auth}

                    #Make request
                    response = requests.get(url, headers=headers,data=data, params=payload)
                    response = json.loads(response.content)

                    # Checks for the existence of the week directory
                    os.chdir(RootDir +'\/' + website['service'] + '\/' + resource_path['name'])
                    if not os.path.exists(timestamps['date']):
                        os.makedirs(timestamps['date'])

                    # Store data into a file
                    with open(os.path.join(RootDir + '\/' + website['service'] + '\/' + resource_path['name'] + '\/' + timestamps['date'],'website_data'+`number`+ '.json'), 'w') as file:
                        json.dump(response,file)


                    # increment the file number by one in line 158
                    number = number + 1
                    # increments start time by 1 minute
                    start_date = three_hours + 100
                    #increments end time by 3 hours
                    three_hours = start_date + 10800

            # Call Compile Data Function
            compileDataRootDir = RootDir + '\/' + website['service'] + '\/' + resource_path['name'] + '\/' + timestamps['date']
            CompileData(compileDataRootDir, resource_path['name'], datapoint, website['service'], timestamps['date'])

# This function uploads the csv file into S3
def UploadToS3(compileDataRootDir,file_name,location):
    print("Uploading to S3...")

    s3 = boto3.client('s3')
    if location == 'overall':
        s3.upload_file(file_name,'logicmonitor-data','overall-status/' + file_name)
    else:
        s3.upload_file(file_name,'logicmonitor-data','response-time/' + file_name)

    # Cleans up the folder and leaves only the compiled data.
    filelist = [ f for f in os.listdir(compileDataRootDir) if f.endswith(".json") ]
    for f in filelist:
        os.remove(os.path.join(compileDataRootDir, f))



# Program Start
timestamps = GetTime()
GetData(websites,timestamps, AccessId, AccessKey, Company)


