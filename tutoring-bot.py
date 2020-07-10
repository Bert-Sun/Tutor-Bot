import discord
import pickle
import asyncio
import tutor_bot
        
# read token file
tokenFile = open("token.txt", "r")
token = tokenFile.read()

# initialize bot and other variables
timeoutDuration = tutor_bot.SECOND * 10
client = tutor_bot.TutorBot(timeoutDuration, 'user_list', 'tutor_manager')

# run the bot
loop = asyncio.get_event_loop()
try:
    # initialize userList from saved file if exists
    loop.run_until_complete(client.start(token))
except KeyboardInterrupt:
    # close connection to Discord
    loop.run_until_complete(client.logout())
finally:
    # run cleanup
    loop.close()
