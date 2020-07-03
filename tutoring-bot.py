import discord
import pickle
import asyncio
import tutor_bot
        
# read token file
tokenFile = open("token.txt", "r")
token = tokenFile.read()

# initialize bot and other variables
timeoutDuration = tutor_bot.SECOND * 10
client = tutor_bot.TutorBot(timeoutDuration)

# run the bot
loop = asyncio.get_event_loop()
try:
    # initialize userList from saved file if exists
    try:
        userListFile = open('user_list', 'rb')
        client.userList = pickle.load(userListFile)
        userListFile.close()
        print(client.userList)
        print("done")
    except:
        client.userList = dict()
    loop.run_until_complete(client.start(token))
except KeyboardInterrupt:
    # close connection to Discord
    loop.run_until_complete(client.logout())
finally:
    # run cleanup
    loop.close()
    userListFile = open('user_list', 'wb')
    pickle.dump(client.userList, userListFile)
    userListFile.close()
