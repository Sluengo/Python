#!/usr/bin/env python3

# Importing boto3, the SDK that allows Python to talk to AWS. Datetime is the library that lets you create date objects.
import boto3
import datetime

# Returns the desired cutoff time. Right now, set to 6 months.
def GetCutOffTime():
    now = datetime.datetime.now()
    epoch = datetime.datetime(1970,1,1)
    cutoff = now - datetime.timedelta(days=182) # Change this to appropriate time frame in days.
    cutoff = int((cutoff - epoch).total_seconds())
    return cutoff


# Returns the names of the log groups.
def CollectLogGroupNames(client):
    logNames=[]
    response = client.describe_log_groups()
    logGroups = response['logGroups']
    for log in logGroups:
        logNames.append(log['logGroupName'])
    return logNames

# Returns the logs that are earlier than the cutoff date.
def LogsBeforeCutoff(logs, cutoff):
        neededLogs=[]
        for stream in logs:
            if 'lastEventTimestamp' in stream:
                timestamp = stream['lastEventTimestamp']
                timestamp = int(str(timestamp)[:-3])
                if timestamp < cutoff:
                        neededLogs.append(stream['logStreamName'])
        return neededLogs

# Deletes the logs that are earlier than the cutoff date.
def DeleteLogs(client, logGroup, neededLogs):
    for log in neededLogs:
        response = client.delete_log_stream(logGroupName=logGroup, logStreamName=log)

# Main Program.
def Main():
    client = boto3.client('logs') # Connects to AWS Cloudwatch
    cutoff = GetCutOffTime()
    logGroups = CollectLogGroupNames(client)

    for logGroup in logGroups:
        response = client.describe_log_streams(logGroupName=logGroup,orderBy='LastEventTime')
        neededLogs = LogsBeforeCutoff(response['logStreams'], cutoff)
        print(logGroup)
        print("Logs to Delete:")
        print(neededLogs)
        print("-------------------------------------")
        #DeleteLogs(client, logGroup, neededLogs)

# Run Main.
Main()
