import discord

subjects = {'math': 0x1, 'hist': 0x2, 'geo': 0x4, 'bio': 0x8, 'chem': 0x10, 'physics': 0x20, 'comp sci': 0x40}

class TutorUser:
#dasf

#comment comment
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

    async def on_ready(self):
        print ("Logged on as %s" % (self.user))
        self.userList = dict()

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content == "!fakejoin":
            await self.on_member_join(message.author)
        
    async def on_member_join(self, member):
        # add user to internal list of users if not already present
        if hash(member) not in self.userList:
            self.userList[hash(member)] = TutorUser()
        server = member.guild
        overwrites = {
                server.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True)
        }
        # create a new channel that only the new joined user can access 
        privChannelDescription = "%s" % (hash(member))
        privChannelCategory = discord.utils.get(server.categories, name='Private Servers')
        newChannel = await server.create_text_channel("Your Private Channel", overwrites=overwrites, category=privChannelCategory, topic=privChannelDescription)
        await newChannel.send('WELCOME MESSAGE PLACEHOLDER')
        # give the new user a role
        try:
            newUserRole = discord.utils.get(server.roles, name='test_role')
            await member.add_roles(newUserRole)
        except:
            print("could not add role to user %s" % (member.nick))
        # send emoji reaction message
        helpMessage = await newChannel.send('REACTION MESSAGE')
        self.userList[hash(member)].helpMessageId = helpMessage.id


    async def on_reaction_add(self, reaction, user):
        if reaction.message.id != self.userList[hash(user)].helpMessageId:
            return
        await reaction.message.channel.send("you reacted with %s" % (str(reaction.emoji)))

tokenFile = open("token.txt", "r")
token = tokenFile.read()

client = TutoringBot()
client.run(token)
