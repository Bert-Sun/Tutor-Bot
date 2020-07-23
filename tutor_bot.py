import discord
import asyncio
import logging
import pickle
import time

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S', level=logging.INFO)
textColour = ''

SECOND = 1
MINUTE = 60
HOUR = 3600
DAY = 86400

subjectEmojis = {'math': '🔰', 'cs': '🖥️', 'physics': '💡', 'chem': '🧪', 'bio': '🧬', 'engessay': '📝', 'french': '⚜️', 'other': '❓'}
subjects = ['math', 'cs', 'physics', 'chem', 'bio', 'eng', 'fre', 'other']
subjectRoleNames = ['Math', 'Computer Science', 'Physics', 'Chemistry', 'Biology', 'English', 'French', 'Misc']


class Tutor:
    # 
    def __init__(self):
        self.questionsAnswered = 0
        self.subjects = list()
        self.lastQuestion = 0
        self.id = None
        self.busy = False


class TutorManager:

    def __init__(self):
        # dict storing subject->list of tutor ids
        self.subjectTutors = dict()
        # dict storing id->tutor
        self.tutorList = dict()
        for subject in subjects:
            self.subjectTutors[subject] = list()

    def add_tutor(self, tutor):
        # overwrites tutor if tutor already exists, otherwise add tutor
        if tutor.id == None:
            return
        self.tutorList[tutor.id] = tutor
        for subject in subjects:
            # check if tutor was unsubscribed from subject
            if subject not in tutor.subjects and tutor.id in self.subjectTutors[subject]:
                # remove tutor from subject
                self.subjectTutors[subject].remove(tutor.id)

            # check if tutor was newly subscribed to subject
            if subject in tutor.subjects and tutor.id not in self.subjectTutors[subject]:
                # add tutor to subject
                self.subjectTutors[subject].append(tutor.id)
            # other scenarios such as tutor remaining (un)subscribed require no changes to list
    
    def request_tutor(self, subject):
        # gets a tutor for the specific subject
        assignedTutor = None
        for tutor in self.subjectTutors[subject]:
            tutor = self.tutorList[tutor]
            if tutor.busy:
                continue
            if assignedTutor == None:
                assignedTutor = tutor
            elif assignedTutor.lastQuestion > tutor.lastQuestion:
                assignedTutor = tutor
        if assignedTutor != None:
            # set assigned tutor to busy status
            self.tutorList[assignedTutor.id].busy = True
        return assignedTutor

    def mark_done(self, tutorId):
        self.tutorList[tutorId].busy = False
        self.tutorList[tutorId].lastQuestion = time.time()

    def get_tutor_by_id(self, tutorId):
        return self.tutorList.get(tutorId)




class TutorUser:

    def __init__(self):
        self.__subscribedSubjects = 0
        self.helpMessageId = None
        self.privateChannelId = None
        self.assignedTutor = None

        self.subjects = {'math': 0x1, 'hist': 0x2, 'geo': 0x4, 'bio': 0x8, 'chem': 0x10, 'physics': 0x20, 'comp sci': 0x40}

    def subscribe_to(self, subject):
        # subscribes the user to a subject using the bitmask
        subject = self.subjects[subject]
        if(not (self.__subscribedSubjects & subject)):
            self.__subscribedSubjects ^= subject

    def unsubscribe_to(self, subject):
        # unsubscribes the user to a subject using the bitmask
        subject = self.subjects[subject]
        if(self.__subscribedSubjects & subject):
            self.__subscribedSubjects ^= subject

    def is_subscribed(self, subject):
        # returns whether a user is subscribed to a subject or not
        return bool(self.__subscribedSubjects & self.subjects[subject])

class TutorBot(discord.Client):

    def __init__(self, timeoutDuration, userListFilePath, tutorManagerFilePath):
        super().__init__()
        self.userList = dict()
        self.userTimeoutList = dict()
        self.tutorManager = TutorManager()
        self.timeoutDuration = timeoutDuration
        self.userListFilePath = userListFilePath
        self.tutorManagerFilePath = tutorManagerFilePath
        try:
            userListFile = open(userListFilePath, 'rb')
            self.userList = pickle.load(userListFile)
            userListFile.close()
        except:
            self.userList = dict()
        try:
            tutorManagerFile = open(tutorManagerFilePath, 'rb')
            self.tutorManager = pickle.load(tutorManagerFile)
            tutorManagerFile.close()
        except:
            self.tutorManager = TutorManager()

    async def on_ready(self):
        logging.info (textColour+"Logged on as %s" % (self.user))
        # iterate through all users 

        for user in self.get_all_members():
            # see if user joined during server downtime and add them to internal memory if so
            if user.id not in self.userList:
                self.userList[user.id] = TutorUser()
            # if user is offline set a timeout for them
            if user.status == discord.Status.offline:
                await self.set_user_timeout(user)
            # if user is online check if they have a private channel, if not create one for them
            elif user.status != discord.Status.offline:
                if self.userList[user.id].privateChannelId == None:
                    self.loop.create_task(self.create_private_channel(user))

    async def on_message(self, message):
        botAdminRole = discord.utils.get(message.author.guild.roles, name='Tutor Bot Admin')
        tutorRole = discord.utils.get(message.author.guild.roles, name='Oracle Tutor')
        # return if message is self
        if message.author == self.user:
            return
        # force creation of new private channel
        if message.content == "!channel" and botAdminRole in message.author.roles:
            await self.create_private_channel(message.author)
        # call on_member_join function
        if message.content == '!fakejoin' and botAdminRole in message.author.roles:
            await self.on_member_join(message.author)
        # delete all created private channels
        elif message.content == "!prune" and botAdminRole in message.author.roles:
            privChannelCategory = discord.utils.get(message.guild.categories, name='Your Private Channels')
            for channel in privChannelCategory.channels:
                await self.delete_user_channel(channel, int(channel.topic))
        # refresh tutor list
        elif message.content.split()[0] == "!refreshtutors" and botAdminRole in message.author.roles:
            server = message.author.guild
            # check if the server is large, and request offline users if so
            if server.large:
                self.request_offline_members(server)
            # for each user check if they are a tutor
            tutorRole = discord.utils.get(server.roles, name='Oracle Tutor')
            for user in message.author.guild.members:
                if tutorRole in user.roles:
                    # update that tutor
                    self.loop.create_task(self.update_tutor(user))
        elif message.content == '!done' and tutorRole in message.author.roles:
            # check if tutor who sent message is the assigned tutor
            tutorRequestee = self.get_user(int(message.channel.topic))
            if self.userList[tutorRequestee.id].assignedTutor != message.author.id:
                await message.channel.send("You are not the assigned tutor to this channel!")
                return
            # revoke tutor permissions and mark them as done
            await message.channel.set_permissions(message.author, overwrites=None)
            self.tutorManager.mark_done(message.author.id)
            # mark the user as not having an assigned tutor anymore
            self.userList[tutorRequestee.id].assignedTutor = None

        
    async def on_member_join(self, member):
        server = member.guild
        # give the new user welcome role
        await self.give_user_role(member, 'welcome role')
        # send welcome message in welcome channel
        welcomeChannel = discord.utils.get(server.channels, name='welcome')
        rulesChannel = discord.utils.get(server.channels, name='rules-and-procedures')
        welcomeMessage = ('Welcome, {user}! ' +
                          'We offer free online homework help and targeted tutoring for topics in Science, Math, English, French, Computer Science, and more! ' +
                          'Please read the rules on the {rules} channel before you begin. ' +
                          'Afterwards, hop on over to the private channel created exclusively for you and our tutors! You can find it under \'Your Private Channels\'.').format(
                             rules=rulesChannel.mention, user=member.mention
                         )
        await welcomeChannel.send(welcomeMessage)
        # add user to internal list of users if not already present
        if member.id not in self.userList:
            self.userList[member.id] = TutorUser()
        # create new private channel for user
        #if self.userList[member.id].privateChannelId == None:
        await self.create_private_channel(member)

    # use on_raw_reaction_add to get reactions to messages not in message cache (such as messages sent before bot startup)
    async def on_raw_reaction_add(self, payload):
        # check if reactor is bot client, if so return
        if payload.user_id == self.user.id:
            return
        # check if the reacted message is the user's help message
        if payload.message_id == self.userList[payload.user_id].helpMessageId:
            # select the correct text channel
            server = payload.member.guild
            textChannel = server.get_channel(payload.channel_id)
            # find the user who added the reaction
            user = server.get_member(payload.user_id)
            emoji = str(payload.emoji)
            # find the subject selected
            subject = None
            for key, value in subjectEmojis.items():
                if value == emoji:
                    subject = key
                    break
            if subject == None:
                await textChannel.send("That is not a valid subject emoji. Try again.")
                return
            # assign the tutor to the channel
            await self.assign_tutor(payload.user_id, textChannel, subject)

    async def on_member_update(self, before, after):
        logging.debug (textColour+"%s, %s" %(before.id, after.id))
        # check if user status has changed
        if before.status != after.status:
            # check if user is offline
            if after.status == discord.Status.offline:
                logging.debug (textColour+"scheduling timeout")
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

    async def close(self):
        # store the user list into persistent memory
        userListFile = open(self.userListFilePath, 'wb')
        pickle.dump(self.userList, userListFile)
        userListFile.close()
        # store the tutor manager into memory as well
        tutorManagerFile = open(self.tutorManagerFilePath, 'rb')
        self.tutorManager = pickle.load(tutorManagerFile)
        tutorManagerFile.close()
        # close connection to discord
        await super().close()

    async def create_private_channel(self, member):
        server = member.guild
        # create text channel overwrites to make the channel inaccessible to all users except for the joined user
        permissions = {
                server.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True)
        }
        # create a new channel that only the new joined user can access 
        privChannelDescription = "%s" % (member.id)
        privChannelCategory = discord.utils.get(server.categories, name='Your Private Channels')
        newChannel = await server.create_text_channel("Your Private Channel", category=privChannelCategory, topic=privChannelDescription)
        await newChannel.set_permissions(member, read_messages=True)
        await newChannel.set_permissions(server.default_role, read_messages=False)
        # send a welcome message
        await newChannel.send(('Welcome, {user}, to your very own private channel on Oracle Tutoring! ' +
                              'Here you can access all of our educational resources with complete anonymity. '+
                              'Read the instructions below to ask a tutor to join this channel and help you.').format(user=member.mention))
        await newChannel.send('On the message below you can select the specific curricular subject that would like help with. ' +
                              'To invite a tutor that specializes in a subject, click on the corresponding button for that subject')
        # store the channel id internally
        self.userList[member.id].privateChannelId = newChannel.id
        # send emoji reaction message
        helpMessageId = await self.send_help_message(newChannel)
        self.userList[member.id].helpMessageId = helpMessageId

    async def send_help_message(self, channel):
        helpMessage = await channel.send(('Math:                           {math}\n' +
                                             'Computer Science:   {cs}\n' +
                                             'Physics:                       {physics}\n' +
                                             'Chemistry:                  {chem}\n' +
                                             'Biology:                        {bio}\n' +
                                             'Essay Help:                 {engessay}\n' +
                                             'French:                        {french}\n' +
                                             'Other:                          {other}\n'
                                            ).format(**subjectEmojis))
        # react with the subject emojis for easy access to user
        for key, value in subjectEmojis.items():
            try:
                await helpMessage.add_reaction(value)
            except:
                logging.error (textColour+"error adding %s emoji" % (key))
        # pin the message for future reference
        await helpMessage.pin()
        return helpMessage.id

    async def user_timeout(self, timeout, channel, userId):
        while self.loop.time() < timeout:
            await asyncio.sleep(5)
        # delete reference to the task
        del self.userTimeoutList[userId]
        await self.delete_user_channel(channel, userId)

    async def delete_user_channel(self, channel, userId):
        await channel.delete()
        # delete reference to the privateChannelId
        self.userList[userId].privateChannelId = None
        logging.debug (textColour+"deleted private channel for user %s" % (userId))

    async def set_user_timeout(self, user):
        # return if user already has a set timeout
        if self.userTimeoutList.get(user.id) != None:
            return
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

    async def assign_tutor(self, userId, channel, subject):
        # check if the user already has a tutor
        if self.userList[userId].assignedTutor != None:
            await channel.send("You already have an assigned Tutor!")
            return
        assignedTutor = self.tutorManager.request_tutor(subject)
        # check if there are available tutors
        if assignedTutor == None:
            await channel.send("Sorry, we are unable to help you at this time. Please try again later.")
            return
        assignedTutor = self.get_user(assignedTutor.id)
        tutorRequestee = self.get_user(userId)
        # assign tutor to user
        self.userList[userId].assignedTutor = assignedTutor.id
        await channel.set_permissions(assignedTutor, read_messages=True)
        await channel.send("Hi %s, you have been assigned to work with %s on %s!" % (assignedTutor.mention, tutorRequestee.mention, subjectRoleNames[subject.index(subject)]) )

    async def give_user_role(self, member, roleName):
        role = discord.utils.get(member.guild.roles, name=roleName)
        if role == None:
            logging.error('%s is not a valid role name!' % (roleName) )
        else:
            try:
                await member.add_roles(role)
            except:
                logging.error("could not give role %s to user %s" %(roleName, member.display_name) )

    async def update_tutor(self, tutor):
        # copy existing data of tutor
        newTutor = self.tutorManager.get_tutor_by_id(tutor.id)
        # if tutor does not exist then initialize the tutor
        if newTutor == None:
            newTutor = Tutor()
            newTutor.id = tutor.id
        # overwrite existing subject subscriptions for tutor
        newTutor.subjects = list()
        for i in range(len(subjects)):
            subjectRole = discord.utils.get(tutor.guild.roles, name='%s Tutor' % (subjectRoleNames[i]))
            if subjectRole in tutor.roles:
                newTutor.subjects.append(subjects[i])
        # add tutor to TutorManager
        self.tutorManager.add_tutor(newTutor)
