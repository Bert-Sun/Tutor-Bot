import discord
import pickle
import asyncio
import tutor_bot
import datetime
        
# read token file
tokenFile = open("token.txt", "r")
token = tokenFile.read()

# initialize bot and other variables
timeoutDuration = tutor_bot.DAY * 1
# office hours should be in UTC time
officeHours = [(datetime.time(13,0), datetime.time(17,0))] # 9-13 eastern time
client = tutor_bot.TutorBot(timeoutDuration, 'user_list', 'tutor_manager', officeHours)

# run the bot
loop = asyncio.get_event_loop()
try:
    # initialize userList from saved file if exists
    loop.run_until_complete(client.start(token))
except KeyboardInterrupt:
    # close connection to Discord
    loop.run_until_complete(client.close())
finally:
    # run cleanup
    loop.close()
