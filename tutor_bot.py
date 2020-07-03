import discord
import asyncio
import logging

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S', level=logging.DEBUG)

SECOND = 1
MINUTE = 60
HOUR = 3600
DAY = 86400

subjects = {'math': 0x1, 'hist': 0x2, 'geo': 0x4, 'bio': 0x8, 'chem': 0x10, 'physics': 0x20, 'comp sci': 0x40}
subjectEmojis = {'math': '🔢', 'science': '👩‍🔬'}

class TutorUser:

    def __init__(self):
        self.__subscribedSubjects = 0
        self.helpMessageId = None
        self.privateChannelId = None

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

class TutorBot(discord.Client):

    def __init__(self, timeoutDuration):
        super().__init__()
        self.userList = dict()
        self.userTimeoutList = dict()
        self.tutorList = list()
        self.timeoutDuration = timeoutDuration

    async def on_ready(self):
        logging.info ("Logged on as %s" % (self.user))
        # load all offline_members
        # await self.request_offline_members(self.guilds)
        # iterate through all users 
        for user in self.users:
            # see if user joined during server downtime and add them to internal memory if so
            if user.id not in self.userList:
                self.userList[user.id] = TutorUser()
            # if user is offline set a timeout for them
            if user.status == offline:
                await self.set_user_timeout(user)
            # if user is online check if they have a private channel, if not create one for them
            elif user.status != offline:
                await self.create_private_channel(user)

    async def on_message(self, message):
        botAdminRole = discord.utils.get(message.author.guild.roles, name='Tutor Bot Admin')
        if message.author == self.user:
            return
        # create new private channel
        if message.content == "!fakejoin" and botAdminRole in message.author.roles:
            await self.on_member_join(message.author)
            print(self.userList[message.author.id].privateChannelId)
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
        # create new private channel for user
        if self.userList[member.id].privateChannelId == None:
            await self.create_private_channel(member)

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

    async def on_member_update(self, before, after):
        logging.debug ("%s, %s" %(before.id, after.id))
        # check if user status has changed
        if before.status != after.status:
            # check if user is offline
            if after.status == discord.Status.offline:
                logging.debug ("scheduling timeout")
                await self.set_user_timeout(before)
            # check if user is coming online
            elif after.status != discord.Status.offline:
                # cancel timeout task, if exists
                timeoutTask = self.userTimeoutList.get(before.id)
                if timeoutTask != None:
                    timeoutTask.cancel()
                # create a private channel for user if does not exist
                if self.userList[after.id].privateChannelId == None:
                    await self.create_private_channel(after)

    async def create_private_channel(self, member):
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
            logging.error ("could not add welcome role to user %s" % (member.display_name))
        # store the channel id internally
        self.userList[member.id].privateChannelId = newChannel.id
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
                logging.error ("error adding %s emoji" % (key))
        # pin the message for future reference
        await helpMessage.pin()
        self.userList[member.id].helpMessageId = helpMessage.id

    async def user_timeout(self, timeout, channel, userId):
        while self.loop.time() < timeout:
            await asyncio.sleep(5)
        await channel.delete()
        # delete reference to the privateChannelId
        self.userList[userId].privateChannelId = None
        # delete reference to the task
        del self.userTimeoutList[userId]
        logging.debug ("deleted private channel for user %s" % (userId))

    async def set_user_timeout(self, user):
        # set user timeout
        timeout_time = self.loop.time() + self.timeoutDuration
        # store the task if necessary to cancel in future
        userPrivChannelId = self.userList[user.id].privateChannelId
        # check if the private channel id is valid
        if userPrivChannelId == None:
            return
        userPrivChannel = user.guild.get_channel(userPrivChannelId)
        # schedule the task to be run
        self.userTimeoutList[user.id] = self.loop.create_task(self.user_timeout(timeout_time, userPrivChannel, user.id))
        
