import discord
import pickle
import asyncio

subjects = {'math': 0x1, 'hist': 0x2, 'geo': 0x4, 'bio': 0x8, 'chem': 0x10, 'physics': 0x20, 'comp sci': 0x40}
subjectEmojis = {'math': '🔢', 'science': '👩‍🔬'}

debugMode = True

class TutorUser:

    def __init__(self):
        self.__subscribedSubjects = 0
        self.helpMessageId = None

    def subscribe_to(self, subject):
        # subscribes the user to a subject using the bitmask
        subject = subjects[subject]
        if(not (self.__subscribedSubjects & subject)):
            self.__subscribedSubjects ^= subject

    def unsubscribe_to(self, subject):
        # unsubscribes the user to a subject using the bitmask
        subject = subjects[subject]
        if(self.__subscribedSubjects & subject):
            self.__subscribedSubjects ^= subject

    def is_subscribed(self, subject):
        # returns whether a user is subscribed to a subject or not
        return bool(self.__subscribedSubjects & subjects[subject])


class TutoringBot(discord.Client):

    def __init__(self):
        super().__init__()
        self.userList = dict()
        self.tutorList = list()

    async def on_ready(self):
        print ("Logged on as %s" % (self.user))

    async def on_message(self, message):
        botAdminRole = discord.utils.get(message.author.guild.roles, name='Tutor Bot Admin')
        if message.author == self.user:
            return
        # emulate user joining
        if message.content == "!fakejoin" and botAdminRole in message.author.roles:
            await self.on_member_join(message.author)
        # delete all created private channels
        elif message.content == "!prune" and botAdminRole in message.author.roles:
            privChannelCategory = discord.utils.get(message.guild.categories, name='Private Servers')
            for channel in privChannelCategory.channels:
                await channel.delete()
        # register a new tutor
        elif message.content.split()[0] == "!regtutor" and botAdminRole in message.author.roles:
            for newTutor in message.mentions:
                if newTutor not in self.tutorList:
                    self.tutorList.append(newTutor)
        elif message.content == "!ping":
            await message.channel.send("pong")
        
    async def on_member_join(self, member):
        # add user to internal list of users if not already present
        if member.id not in self.userList:
            self.userList[member.id] = TutorUser()
        server = member.guild
        overwrites = {
                server.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True)
        }
        # create a new channel that only the new joined user can access 
        privChannelDescription = "%s" % (member.id)
        privChannelCategory = discord.utils.get(server.categories, name='Private Servers')
        newChannel = await server.create_text_channel("Your Private Channel", overwrites=overwrites, category=privChannelCategory, topic=privChannelDescription)
        # send a welcome message and pin it
        welcomeMessage = await newChannel.send('WELCOME MESSAGE PLACEHOLDER')
        await welcomeMessage.pin()
        # give the new user a role
        try:
            newUserRole = discord.utils.get(server.roles, name='test_role')
            await member.add_roles(newUserRole)
        except:
            print("could not add welcome role to user %s" % (member.display_name))
        # send emoji reaction message
        helpMessage = await newChannel.send(('To request for help in a specific subject, react with the following emojis:\n'+
                                             'Math: {math}\n' +
                                             'Science: {science}\n' +
                                             'English: \n'
                                            ).format(**subjectEmojis))
        # react with the subject emojis for easy access to user
        for key, value in subjectEmojis.items():
            try:
                await helpMessage.add_reaction(value)
            except:
                print("error adding %s emoji" % (key))
        # pin the message for future reference
        await helpMessage.pin()
        self.userList[member.id].helpMessageId = helpMessage.id

    # use on_raw_reaction_add to get reactions to messages not in message cache (such as messages sent before bot startup)
    async def on_raw_reaction_add(self, payload):
        # check if reactor is bot client, if so return
        if payload.user_id == self.user.id:
            return
        # check if the reacted message is the user's help message
        if payload.message_id != self.userList[payload.user_id].helpMessageId:
            return
        # select the correct text channel
        server = payload.member.guild
        textChannel = server.get_channel(payload.channel_id)
        # find the user who added the reaction
        user = server.get_member(payload.user_id)
        await textChannel.send("%s, you have been assigned to work with %s" % (self.tutorList[0].mention, user.display_name))
        print(str(payload.emoji))

        
# read token file
tokenFile = open("token.txt", "r")
token = tokenFile.read()

# initialize bot and other variables
client = TutoringBot()

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
