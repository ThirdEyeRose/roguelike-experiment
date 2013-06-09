#Graphics Library Input
import libtcodpy as libtcod
import math
import textwrap
import shelve

#Constant variables

#Actual Size of the Window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

#size of the map portion shown on-screen
CAMERA_WIDTH = 80
CAMERA_HEIGHT = 43

#size of the map
MAP_WIDTH = 100
MAP_HEIGHT = 100

#sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50
CHARACTER_SCREEN_WIDTH = 30

#Dungeon Generation
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 45

#Spell Variables
HEAL_AMOUNT = 40
LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25

#experience and level ups
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150
LEVEL_SCREEN_WIDTH = 40

#FOV Setup
FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

LIMIT_FPS = 20

color_dark_wall = libtcod.Color(56, 50, 19)
color_light_wall = libtcod.Color(74, 66, 25)
color_dark_ground = libtcod.Color(102, 94, 46)
color_light_ground = libtcod.Color(140, 133, 93)

#Set up Font
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)

#Initialize Window
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
libtcod.sys_set_fps(LIMIT_FPS)

class World:
	#this class is specific to each save game.  Holds all world data
	def __init__(self, objects = None):
		self.objects = objects
		self.maps = {}
		
class Map:
	#this class stores map information so that maps can be persistent
	def __init__(self, name):
		self.name = name
		self.tiles = []
		self.objects = []
		self.portals = []

class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on the screen.
	def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item = None, equipment = None, portal = None):
		self.x = x
		self.y = y
		self.char = char
		self.color = color
		self.name = name
		self.blocks = blocks
		self.always_visible = always_visible
		self.fighter = fighter
		if self.fighter:
			self.fighter.owner = self
		self.ai = ai
		if self.ai:
			self.ai.owner = self
		self.item = item
		if self.item:
			self.item.owner = self
		self.equipment = equipment
		if self.equipment:
			self.equipment.owner = self
			#there must be an item component for equipment to act properly
			self.item = Item()
			self.item.owner = self
		self.portal = portal
		if self.portal:
			self.portal.owner = self
	
	def move(self, dx, dy):
		#move by the given amount, if not blocked
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
	
	def move_towards(self, target_x, target_y):
		#vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		
		#normalize it to length 1 (preserving direction), then round it and
		#convert to integer so the movement is restricted to the map grid
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		if is_blocked(self.x + dx, self.y + dy):
			#if blocked, check for a better solution
			#calculate distance of all possible solutions
			#check if blocked, keep lowest
			lowest_dist = None
			for x in range (-1,2):
				for y in range (-1,2):
					new_dx = target_x - self.x + x
					new_dy = target_y - self.y + y
					distance = math.sqrt(new_dx ** 2 + new_dy ** 2)
					if not is_blocked(self.x + new_dx, self.y + new_dy):
						if lowest_dist == None:
							lowest_dist = distance
						if (distance <= lowest_dist) and ((dx,dy) != (new_dx,new_dy)):
							dx = int(round(new_dx / distance))
							dy = int(round(new_dy / distance))
							lowest_dist = distance		
		self.move(dx, dy)
		
	def distance_to(self, other):
		#return the distance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)
		
	def distance(self, x, y):
		#return the distance to some coordinates
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
	
	def draw(self):
		if libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and world.maps['area' + str(depth)].tiles[self.x][self.y].explored):
			#if object is in visible range
			(x, y) = to_camera_coordinates(self.x, self.y)
			#set the color and then draw the character that represents this object at its position
			if x is not None:
				libtcod.console_set_default_foreground(con, self.color)
				libtcod.console_put_char(con, x, y, self.char, libtcod.BKGND_NONE)
		
	def clear(self):
		#erase the character that represents this object
		(x, y) = to_camera_coordinates(self.x, self.y)
		if x is not None:
			libtcod.console_put_char(con, x, y, ' ', libtcod.BKGND_NONE)
		
	def send_to_back(self):
		#make this object be drawn first, so all others appear above it if they're in the same tile
		global world
		world.maps['area' + str(depth)].objects.remove(self)
		world.maps['area' + str(depth)].objects.insert(0, self)

class Fighter:
	#combat related properties and methods (monster, player, NPC)
	def __init__(self, hp, defense, power, xp, mp=0, death_function=None):
		self.base_max_hp = hp
		self.hp = hp
		self.base_max_mp = mp
		self.mp = mp
		self.base_defense = defense
		self.base_power = power
		self.xp = xp
		self.death_function = death_function
		
	@property
	def power(self):
		bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
		return self.base_power + bonus
		
	@property
	def defense(self):  #return actual defense, by summing up the bonuses from all equipped items
		bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
		return self.base_defense + bonus
		
	@property
	def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items
		bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_hp + bonus
		
	@property
	def max_mp(self):  #return actual max_mp, by summing up the bonuses from all equipped items
		bonus = sum(equipment.max_mp_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_mp + bonus
		
	def take_damage(self, damage):
		#apply damage if possible
		if damage > 0:
			self.hp -= damage
			
			#check for death. if there's a death function, call it
			if self.hp <= 0:
				function = self.death_function
				if function is not None:
					function(self.owner)
				if self.owner != player: #yield experience to the player
					player.fighter.xp += self.xp
			
	def attack(self, target):
		#a simple formula for attack damage
		damage = self.power - target.fighter.defense
		
		if damage > 0:
			#make the target take some damage
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
			target.fighter.take_damage(damage)
		else:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')
			
	def heal(self, amount):
		#heal by the given amount, without going over the maximum
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp
			
class BasicMonster:
	#AI for a basic monster.
	def take_turn(self):
		#a basic monster takes its turn. If you can see it, it can see you
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
		
			#move monster towards player if far away
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
				
			#close enough, attack! (if the player is still alive)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)

class ConfusedMonster:
	#AI for a temporarily confused monster.
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns
	
	def take_turn(self):
		if self.num_turns > 0: #still confused...
			#move in a random direction, and decrease the number of turns confused
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.num_turns -= 1
		else:
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)
				
class Item:
	def __init__(self, use_function=None):
		self.use_function = use_function
		
	#an item that can be picked up and used.
	def pick_up(self):
		#add to the player's inventory and remove from the map
		if len(inventory) >= 26:
			message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
		else:
			inventory.append(self.owner)
			world.maps['area' + str(depth)].objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', libtcod.green)
		
		#special case: automatically equip, if the corresponding equipment slot is unused
		equipment = self.owner.equipment
		if equipment and get_equipped_in_slot(equipment.slot) is None:
			equipment.equip()			
			
	def use(self):
		#special case: if the object has the Equipment component, the "use" action is to equip/dequip
		if self.owner.equipment:
			self.owner.equipment.toggle_equip()
			return
		#just call the "use_function" if it is defined
		if self.use_function is None:
			message('The ' + self.owner.name + ' cannot be used.')
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner) #destroy after use, unless it was cancelled for some reason
				
	def drop(self):
		#add to the map and remove from the player's inventory. also, place it at the player's coordinates
		world.maps['area' + str(depth)].objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y
		message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
		if self.owner.equipment:
			self.owner.equipment.dequip()

class Equipment:
	#an object that can be equipped, yielding bonuses. automatically adds the Item component.
	def __init__(self, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0, max_mp_bonus=0):
		self.slot = slot
		self.is_equipped = False
		self.power_bonus = power_bonus
		self.defense_bonus = defense_bonus
		self.max_hp_bonus = max_hp_bonus
		self.max_mp_bonus = max_mp_bonus
		
	def toggle_equip(self): #toggle equpi/dequip status
		if self.is_equipped:
			self.dequip()
		else:
			self.equip()
			
	def equip(self):
		#if the slot is already being used, dequip whatever is there first
		old_equipment = get_equipped_in_slot(self.slot)
		if old_equipment is not None:
			old_equipment.dequip()
			
		#equip object and show a message about it
		self.is_equipped = True
		message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)
		
	def dequip(self):
		#dequip objects and show a message about it
		if not self.is_equipped: return
		self.is_equipped = False
		message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)
		
class Portal:
	#this class records relevant information regarding map exits
	def __init__(self, dest_map, dest_portal_index):
		self.dest_map = dest_map[dest_portal_index]
		#when portals are created, they also record data about
		#which portal they are linked to.  This should be in 
		#the form of: world.maps['MAPNAME'].portals[PORTALINDEX]
		#For simplicity's sake, at the beginning, each map will
		#only have 2 portal indices - 0 for up, 1 for down
		
class Tile:
	#a tile of the map and its properties
	def __init__(self, blocked, explored=False, block_sight = None):
		self.blocked = blocked
		self.explored = explored
		
		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight
		
class Rect:
	#a rectangle on the map. Used to characterize a room
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h
		
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)
		
	def intersect(self, other):
		#returns true if this rectangle intersects with another one
		return (self.x1 <= other.x2 and self.x2 > other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)

def new_game():
	global player, inventory, game_msgs, game_state, depth, world
	
	#create new world
	world = World()
	
	#create the object representing the player
	fighter_component = Fighter(hp=100, mp=5, defense=1, power=2, xp=0, death_function = player_death)
	player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)
	
	player.level = 1
	
	#Create Map
	#depth = 0
	depth = 1 #testing
	make_map()
	
	initialize_fov()
	
	#Initialize Game States and Player Inventory
	game_state = 'playing'
	inventory = []
	
	#create list of game messages and their colors. starts empty
	game_msgs = []
	
	#A warm welcoming message!
	message('Welcome stranger! Prepare to perish in the Universal Reference Frame.', libtcod.red)
	
	#starting equipment: a dagger
	equipment_component = Equipment(slot='right hand', power_bonus=2)
	obj = Object(0, 0, '-', 'dagger', libtcod.sky, equipment=equipment_component)
	inventory.append(obj)
	equipment_component.equip()
	obj.always_visible = True
	
def play_game():
	global camera_x, camera_y, key, mouse
	
	player_action = None
	mouse = libtcod.Mouse()
	key = libtcod.Key()
	
	(camera_x, camera_y) = (0,0)
	
	#Start Main Loop
	while not libtcod.console_is_window_closed():
	
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
	
		#render all objects in list
		render_all()
	
		#Present the changes (flush) to the screen
		libtcod.console_flush()
		
		#check for level up
		check_level_up()
	
		#erase all objects at their old locations, before they move
		for object in world.maps['area' + str(depth)].objects:
			object.clear()
	
		#handle keys and exit game if needed
		player_action = handle_keys()
		if player_action == 'exit':
			save_game()
			break

		#let monsters take their turn
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in world.maps['area' + str(depth)].objects:
				if object.ai:
					object.ai.take_turn()

def save_game():
	#open a new empty shelve (possibly overwriting an old one) to write the game data
	file = shelve.open('savegame', 'n')
	file['world'] = world
	file['player_index'] = world.maps['area' + str(depth)].objects.index(player) #index of player in objects list
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['depth'] = depth
	file.close()

def load_game():
	#open the previously saved shelve and load the game data
	global player, inventory, game_msgs, game_state, stairs_up, stairs_down, world
	global depth
	
	file = shelve.open('savegame', 'r')
	world = file['world']
	player = world.maps['area' + str(depth)].objects[file['player_index']] #get index of player in objects list and access it
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	depth = file['depth']
	file.close()
	
	initialize_fov()
	
def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True
	libtcod.console_clear(con)
	
	#create the FOV map, according to the generated map
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not world.maps['area' + str(depth)].tiles[x][y].block_sight, not world.maps['area' + str(depth)].tiles[x][y].blocked)
		
def player_death(player):
	#the game ended!
	global game_state
	message('You died!', libtcod.red)
	game_state = 'dead'
	
	#for added effect, transform the player into a corpse!
	player.char = '%'
	player.color = libtcod.dark_red
	
def monster_death(monster):
	#transform it into a nasty corpse! it doesn't block, can't be attacked and doesn't move
	message(monster.name.capitalize() + ' is dead!', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()
		
def player_move_or_attack(dx, dy):
	global fov_recompute
	
	#the coordinates the player is moving to/attacking
	x = player.x + dx
	y = player.y + dy
	
	#try to find an attackable object there
	target = None
	for object in world.maps['area' + str(depth)].objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break
			
	#attack if target found, move otherwise
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute = True
		
#create function to handle key presses
def handle_keys():
	global key

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit'  #exit game
	
	if game_state == 'playing':
		#movement keys
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
			player_move_or_attack(0, -1)
		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
			player_move_or_attack(0, 1)
		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
			player_move_or_attack(-1, 0)
		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
			player_move_or_attack(1, 0)
		elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
			player_move_or_attack(-1, -1)
		elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
			player_move_or_attack(1, -1)
		elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
			player_move_or_attack(-1, 1)
		elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
			player_move_or_attack(1, 1)
		elif key.vk == libtcod.KEY_KP5:
			pass  #do nothing ie wait for the monster to come to you
		else:
			#test for other keys
			key_char = chr(key.c)
			
			if key_char == 'g':
				#pick up an item
				for object in world.maps['area' + str(depth)].objects: #look for an item in the player's tile
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break
						
			if key_char == 'i':
				#show the inventory
				chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()
					
			if key_char == 'd':
				#show the inventory; if an item is selected, drop it
				chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()
					
			if key_char == '>':
				#go down stairs, if the player is on them
				if stairs_down.x == player.x and stairs_down.y == player.y:
					next_level()
					
			if key_char == '<':
				#go up stairs, if the player is on them
				if stairs_up.x == player.x and stairs_up.y == player.y:
					prev_level()
					
			if key_char == 'c':
				#show character info
				level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
				msgbox('Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) + '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) + '\n\nMaximum MP: ' + str(player.fighter.max_mp) +	'\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)
				
			return 'didnt-take-turn'

def get_names_under_mouse():
	global mouse
	
	#return a string with the names of all objects under the mouse
	(x, y) = (mouse.cx, mouse.cy)
	(x, y) = (camera_x + x, camera_y + y) #from screen to map coordinates
	
	#create a list with the names of all objects at the mouse's coordinates and in FOV
	names = [obj.name for obj in world.maps['area' + str(depth)].objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
		
	names = ', '.join(names) #join the names, seperated by commas
	return names.capitalize()

def move_camera(target_x, target_y):
	global camera_x, camera_y, fov_recompute
	
	#new camera coordinates (top left corner of the screen relative to the map)
	x = target_x - CAMERA_WIDTH / 2 #coordinates so that the target is at the center of the screen
	y = target_y - CAMERA_HEIGHT / 2
	
	#make sure the camera doesn't see outside the map
	if x < 0: x = 0
	if y < 0: y = 0
	if x > MAP_WIDTH - CAMERA_WIDTH - 1: x = MAP_WIDTH - CAMERA_WIDTH - 1
	if y > MAP_HEIGHT - CAMERA_HEIGHT - 1: y = MAP_HEIGHT - CAMERA_HEIGHT - 1
	
	if x != camera_x or y != camera_y: fov_recompute = True
	
	(camera_x, camera_y) = (x, y)
	
def to_camera_coordinates(x,y):
	#convert coordinates on the map to coordinates on the screen
	(x, y) = (x - camera_x, y - camera_y)
	
	if (x < 0 or y < 0 or x >= CAMERA_WIDTH or y >= CAMERA_HEIGHT):
		return (None, None)  #if it's outside the view, return nothing
		
	return (x, y)
	
def is_blocked(x, y):
	#first test the map tile
	if world.maps['area' + str(depth)].tiles[x][y].blocked:
		return True
		
	#now check for any blocking objects
	for object in world.maps['area' + str(depth)].objects:
		if object.blocks and object.x == x and object.y == y:
			return True
			
	return False
	
def make_map():
	global stairs_up, stairs_down, depth, world
	
	world.maps['area' + str(depth)] = Map('area' + str(depth))
	#the list of objects with just the player
	world.maps['area' + str(depth)].objects = [player]
			
	#Using the map class			
	if depth == 0:
		#fill map with "blocked" tiles
		world.maps['area' + str(depth)].tiles = [[ Tile(True, explored=True)
			for y in range(MAP_HEIGHT) ]
				for x in range(MAP_WIDTH) ]
		for x in range(1, MAP_WIDTH - 2):
			for y in range(1, MAP_HEIGHT - 2):
				world.maps['area' + str(depth)].tiles[x][y].blocked = False
				world.maps['area' + str(depth)].tiles[x][y].block_sight = False	
			
	else:
		#fill map with "blocked" tiles
		world.maps['area' + str(depth)].tiles = [[ Tile(True)
			for y in range(MAP_HEIGHT) ]
				for x in range(MAP_WIDTH) ]
		
	rooms = []
	num_rooms = 0
	
	for r in range(MAX_ROOMS):
		#random width and height
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		#random position without going out of the boundaries of the map
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
	
		#"Rect" class makes rectangles easier to work with
		new_room = Rect(x, y, w, h)
	
		#run through the other rooms and see if they intersect with this one
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
	
		if not failed:
			#this means there is no intersections, so this room is valid
			
			#"paint" it to the map's tiles
			create_room(new_room)
			place_objects(new_room)
			
			#center coordinates of new room, will be useful later
			(new_x, new_y) = new_room.center()
			
			if num_rooms == 0:
				placed = False
				x = new_x
				y = new_y
				while not placed:
					if not is_blocked(x, y):
						#this is the first room, where the player starts at
						player.x = x
						player.y = y
						placed = True
						if depth != 0:
							#create stairs at the center of the last room
							if depth == 1:
								portal = Portal('area' + str(depth - 1), 0)
							else:
								portal = Portal('area' + str(depth - 1), 1)
							stairs_up = Object(new_x, new_y, '<', 'stairs up', libtcod.white, always_visible = True, portal = portal)
							world.maps['area' + str(depth)].objects.append(stairs_up)
							world.maps['area' + str(depth)].portals.append(stairs_up)
							stairs_up.send_to_back() #so it's drawn below monsters
					else:
						x += 1
			else:
				#all rooms after the first:
				#connect it to the previous room with a tunnel
				
				#center coordinates of previous room
				(prev_x, prev_y) = rooms[num_rooms-1].center()
				
				#draw a coin (random number that is either 0 or 1)
				if libtcod.random_get_int(0, 0, 1) == 1:
					#first move horizontally, then vertically
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					#first move vertically, then horizontally
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)
					
			#finally, append the new room to the list
			rooms.append(new_room)
			num_rooms += 1
			
	#create stairs at the center of the last room
	stairs_down = Object(new_x, new_y, '>', 'stairs down', libtcod.white, always_visible = True)
	world.maps['area' + str(depth)].objects.append(stairs_down)
	stairs_down.send_to_back() #so it's drawn below monsters

	
	
def next_level():
	global depth
	
	#advance to the next level
	message('You decend deeper into the heart of the earth...', libtcod.red)
	depth += 1
	make_map() #create a fresh new level!
	initialize_fov()
	
def prev_level():
	global depth
	
	#advance to the next level
	message('You climb your way out of the earth...', libtcod.red)
	depth -= 1
	make_map() #create a fresh new level!
	initialize_fov()
			
def create_room(room):
	global world
	#go through the tiles in the rectangle and make them passable
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			world.maps['area' + str(depth)].tiles[x][y].blocked = False
			world.maps['area' + str(depth)].tiles[x][y].block_sight = False
			
def create_h_tunnel(x1, x2, y):
	global world
	for x in range(min(x1, x2), max(x1, x2) + 1):
		world.maps['area' + str(depth)].tiles[x][y].blocked = False
		world.maps['area' + str(depth)].tiles[x][y].block_sight = False
		
def create_v_tunnel(y1, y2, x):
	global world
	for y in range(min(y1, y2), max(y1, y2) + 1):
		world.maps['area' + str(depth)].tiles[x][y].blocked = False
		world.maps['area' + str(depth)].tiles[x][y].block_sight = False

def message(new_msg, color = libtcod.white):
	#split the message if necessary, among mulitple lines
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
	
	for line in new_msg_lines:
		#if the buffer is full, remove the first line to make room the new one
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
			
		#add the new line as a tuple, with the text and the color
		game_msgs.append( (line, color) )
		
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#render a bar (HP, experience, etc). first calculate the width of the bar
	bar_width = int(float(value) / maximum * total_width)
	
	#render the background first
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
	
	#now render the bar on top
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
		
	#finally, some centered text with the values
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))
		
def render_all():
	global fov_map, color_light_wall, color_dark_wall
	global color_light_ground, color_dark_ground
	global fov_recompute, level_up_xp
	
	move_camera(player.x, player.y)

	if fov_recompute:
		#recompute FOV if needed (the player moved or something)
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		libtcod.console_clear(con)
		
		for y in range(CAMERA_HEIGHT):
			for x in range(CAMERA_WIDTH):
				(map_x, map_y) = (camera_x + x, camera_y + y)
				visible = libtcod.map_is_in_fov(fov_map, map_x, map_y)
				
				wall = world.maps['area' + str(depth)].tiles[map_x][map_y].block_sight
				if not visible:
					#it's out of the player's FOV
					if world.maps['area' + str(depth)].tiles[map_x][map_y].explored:
					#if it's not visible right now, the player can only see it if it's explored
						if wall:
							libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET )
						else:
							libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET )
				else:
					#it's visible
					if wall:
						libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET )
					else:
						libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET )
					world.maps['area' + str(depth)].tiles[map_x][map_y].explored = True
					
	#draw all objects in the list
	for object in world.maps['area' + str(depth)].objects:
		if object != player:
			object.draw()
	player.draw()
	
	#blit the contents of "con" to the root console
	libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)
	
	#prepare to render the GUI panel
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)
	
	#print the game messages, one line at a time
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1
	
	#show the player's stats
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
	render_bar(1, 2, BAR_WIDTH, 'MP', player.fighter.mp, player.fighter.max_mp, libtcod.light_blue, libtcod.darker_blue)
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	render_bar(1, 3, BAR_WIDTH, 'XP', player.fighter.xp, level_up_xp, libtcod.light_yellow, libtcod.darker_yellow)
	libtcod.console_print_ex(panel, 1, 5, libtcod.BKGND_NONE, libtcod.LEFT, 'Depth ' + str(depth))
	
	#display names of objects under the mouse
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
	
	#blit the contents of "panel" to the root console
	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def place_objects(room):
	#maximum number of monsters per room
	max_monsters = from_depth([[2,1],[3,4],[5,6]])
	
	#chance of each monster
	monster_chances = {}
	monster_chances['orc'] = 80
	monster_chances['troll'] = from_depth([[15,3],[30,5],[60,7]])
	
	#maximum number of items per room
	max_items = from_depth([[1,1],[2,4]])
	
	#chance of each item (by default the have a chance of 0 at level 1, which then goes up)
	item_chances = {}
	item_chances['heal'] = 35
	item_chances['lightning'] = from_depth([[25,4]])
	item_chances['fireball'] = from_depth([[25,6]])
	item_chances['confuse'] = from_depth([[10,2]])	
	item_chances['sword'] = from_depth([[5,4]])
	item_chances['shield'] = from_depth([[15,8]])
	
	#choose random number of monsters
	num_monsters = libtcod.random_get_int(0, 0, max_monsters)
	
	for i in range(num_monsters):
		#choose random spot for this monster
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		if not is_blocked(x, y):
			choice = random_choice(monster_chances)
			if choice == 'orc': #80% chance of getting an orc
				#create an orc
				fighter_component = Fighter(hp=20, defense=0, power=4, xp=35, death_function = monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'o', 'orc', libtcod.light_green, blocks=True, fighter=fighter_component, ai=ai_component)
			elif choice == 'troll':
				#create a troll
				fighter_component = Fighter(hp=30, defense=2, power=8, xp=100, death_function = monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'T', 'troll', libtcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)
			
			world.maps['area' + str(depth)].objects.append(monster)
			
	#choose random number of items
	num_items = libtcod.random_get_int(0, 0, max_items)
	
	for i in range(num_items):
		#choose random spot for this item
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		#only place it if the tile is not blocked
		if not is_blocked(x, y):
			choice = random_choice(item_chances)
			if choice == 'heal': #70%
				#create a healing potion (70% chance)
				item_component = Item(use_function = cast_heal)
				item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component)
			elif choice == 'lightning': #10%
				#create a lightning bolt scroll (10% chance)
				item_component = Item(use_function=cast_lightning)
				item = Object(x, y, '#', 'scroll of lighning bolt', libtcod.light_yellow, item=item_component)
			elif choice == 'fireball': #10%
				#create a fireball scroll (10% chance)
				item_component = Item(use_function=cast_fireball)
				item = Object(x, y, '#', 'scroll of fireball', libtcod.light_yellow, item=item_component)
			elif choice == 'confuse': 
				#create a confuse scroll (10% chance)
				item_component = Item(use_function=cast_confuse)
				item = Object(x, y, '#', 'scroll of confusion', libtcod.light_yellow, item=item_component)
			elif choice == 'sword':
				#create a sword
				equipment_component = Equipment(slot='right hand', power_bonus=3)
				item = Object(x, y, '/', 'sword', libtcod.sky, equipment=equipment_component)
			elif choice == 'shield':
				#create a shield
				equipment_component = Equipment(slot='left hand', defense_bonus=1)
				item = Object(x, y, '[', 'shield', libtcod.darker_orange, equipment=equipment_component)
			
			world.maps['area' + str(depth)].objects.append(item)
			item.send_to_back() #items appear below other objects

def menu(header, options, width):
	global key

	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
	
	#calculate total height for the header (after auto-wrap) and one line per option
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + header_height
	
	#create an off-screen console that represents the menu's window
	window = libtcod.console_new(width, height)
	
	#print the header, with auto-wrap
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
	
	#print all the options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y += 1
		letter_index += 1
		
	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
	
	#present the root console to the player and wait for a key-press
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	
	#convert the ASCII code to an index; if it corresponds to an option, return it
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None

def inventory_menu(header):
	#show a menu with each item of the inventory as an option
	if len(inventory) == 0:
		options = ['Invetory is empty.']
	else:
		options = []
		for item in inventory:
			text = item.name
			#show additional information, in case it's equipped
			if item.equipment and item.equipment.is_equipped:
				text = text + ' (on ' + item.equipment.slot + ')'
			options.append(text)
		
	index = menu(header, options, INVENTORY_WIDTH)
	
	#if an item was chosen, return it
	if index is None or len(inventory) == 0: return None
	return inventory[index].item

def main_menu():
	img = libtcod.image_load('menu_background1.png')
	
	while not libtcod.console_is_window_closed():
		#show the background image, at twice the regular console resolution
		libtcod.image_blit_2x(img, 0, 0, 0)
		
		#show the game's title, and some credits!
		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER, 'The Universal Reference Frame')
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER, 'By Pat East')
		
		#show options and wait for the player's choice
		choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)
		
		if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
			libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		
		if choice == 0: #new game
			new_game()
			play_game()
		elif choice == 1: #load last game
			try:
				load_game()
			except:
				msgbox('\n No saved game to load.\n', 24)
				continue
			play_game()
		elif choice == 2: #quit
			break

def msgbox(text, width=50):
	menu(text, [], width) #use menu() as a sort of "message box"
			
def cast_heal():
	#heal the player
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health.', libtcod.red)
		return 'cancelled'
		
	message('Your wounds start to feel better!', libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)
	
def cast_lightning():
	#find the closest enemy (inside a maximum range) and damage it
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None: #no enemy found within maximum range
		message('No enemy is close enough to strike.', libtcod.red)
		return 'cancelled'
		
	#zap it!
	message('A lightning bolt strikes the ' + monster.name + ' with a loud thunder! The damage is ' + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)
	
def cast_confuse():
	#ask the player for a target to confuse
	message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None: return 'cancelled'
		
	#replace the monster's AI with a "confused" one; after some turns it will restore the old AI
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster #tell the new component who owns it
	message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)

def cast_fireball():
	#ask the player for a target tile to throw a fireball at
	message('Left-click a target tile for the fireball, or right-click to cancel.', libtcod.light_cyan)
	(x,y) = target_tile()
	if x is None: return 'cancelled'
	message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)
	
	for obj in world.maps['area' + str(depth)].objects: #damage every fighter in range, including the player
		if obj.distance(x,y) <= FIREBALL_RADIUS and obj.fighter:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)
	
def closest_monster(max_range):
	#find closest enemy, up to a maximum range, and in the player's FOV
	closest_enemy = None
	closest_dist = max_range + 1
	
	for object in world.maps['area' + str(depth)].objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			#calculate distance between this object and the player
			dist = player.distance_to(object)
			if dist < closest_dist: #it's closer, so remember it
				closest_enemy = object
				closest_dist = dist
	return closest_enemy

def target_tile(max_range=None):
	#return the position of a tile left-clicked in the player's FOV (optionally in a range), or (None,None) if right-clicked
	global key, mouse
	while True:
		#render the screen. this erases the inventory and shows the names of objects under the mouse.
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
		render_all()
		
		(x, y) = (mouse.cx, mouse.cy)
		(x, y) = (camera_x + x, camera_y + y)  #from screen to map coordinates
		
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and (max_range is None or player.distance(x, y) <= max_range)):
			return (x, y)
			
		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			return (None, None) #cancel if the player right-clicked or pressed escape

def target_monster(max_range = None):
	#returns a clicked monster inside FOV up to a range, or None if right-clicked
	while True:
		(x, y) = target_tile(max_range)
		if x is None: #player cancelled
			return None
		
		#return the first clicked monster, otherwise continue looping
		for obj in world.maps['area' + str(depth)].objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj

def check_level_up():
	#see if the player's experience is enough to level-up
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	if player.fighter.xp >= level_up_xp:
		#it is! level up
		player.level += 1
		player.fighter.xp -= level_up_xp
		message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)
		
		choice = None
		while choice == None: #keep asking until choice is made
			choice = menu('Level up! Choose a stat to raise:\n', 
				['Constitution (+20 HP, from ' +str(player.fighter.base_max_hp) + ')',
				'Strength (+1 attack, from ' + str(player.fighter.base_power) + ')',
				'Agility (+1 defense, from ' + str(player.fighter.base_defense) + ')'],
				LEVEL_SCREEN_WIDTH)
			
			if choice == 0:
				player.fighter.base_max_hp += 20
				player.fighter.hp += 20
			elif choice == 1:
				player.fighter.base_power += 1
			elif choice == 2:
				player.fighter.base_defense += 1

def random_choice_index(chances): 
	#choose one option from list of chances, returning its index
	#the dice will land on some number between 1 and the sum of the chances
	dice = libtcod.random_get_int(0, 1, sum(chances))
	
	#go through all chances, keeping the sum so far
	running_sum = 0
	choice = 0
	for w in chances:
		running_sum += w
		
		#see if the dice landed in the part that corresponds wo this choice
		if dice <= running_sum:
			return choice
		choice += 1

def random_choice(chances_dict):
	#choose one option from dictionary of chances, returning its key
	chances = chances_dict.values()
	strings = chances_dict.keys()
	
	return strings[random_choice_index(chances)]

def from_depth(table):
	#returns a value that depends on level. the table specifies what value occurs after each level, default is 0.
	for (value, level) in reversed(table):
		if depth >= level:
			return value
	return 0
	
def get_equipped_in_slot(slot): #returns the equipment in a slot, or None if it's empty
	for obj in inventory:
		if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
			return obj.equipment
	return None
	
def get_all_equipped(obj): #returns a list of equipped items
	if obj == player:
		equipped_list = []
		for item in inventory:
			if item.equipment and item.equipment.is_equipped:
				equipped_list.append(item.equipment)
		return equipped_list
	else:
		return [] #other objects have no equipment
	
main_menu()
