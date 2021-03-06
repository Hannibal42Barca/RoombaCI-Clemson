''' Roomba_Accel_Data_Test.py
Purpose: Get Acceleration data as Roomba moves a set distance
IMPORTANT: Must be run using Python 3 (python3)
Last Modified: 6/29/2018
'''
## Import libraries ##
import serial
import time
import RPi.GPIO as GPIO

import RoombaCI_lib
from RoombaCI_lib import DHTurn

import math

## Variables and Constants ##
global Xbee # Specifies connection to Xbee
Xbee = serial.Serial('/dev/ttyUSB0', 115200) # Baud rate should be 115200
# LED pin numbers
yled = 5
rled = 6
gled = 13

# Roomba Constants
WHEEL_DIAMETER = 72 # millimeters
WHEEL_SEPARATION = 235 # millimeters
WHEEL_COUNTS = 508.8 # counts per revolution
DISTANCE_CONSTANT = (WHEEL_DIAMETER * math.pi)/(WHEEL_COUNTS) # millimeters/count
TURN_CONSTANT = (WHEEL_DIAMETER * 180)/(WHEEL_COUNTS * WHEEL_SEPARATION) # degrees/count

epsilon = 0.5 # smallest resolution of angle

## Functions and Definitions ##
''' Displays current date and time to the screen
	'''
def DisplayDateTime():
	# Month day, Year, Hour:Minute:Seconds
	date_time = time.strftime("%B %d, %Y, %H:%M:%S", time.gmtime())
	print("Program run: ", date_time)

## -- Code Starts Here -- ##
# Setup Code #
GPIO.setmode(GPIO.BCM) # Use BCM pin numbering for GPIO
DisplayDateTime() # Display current date and time

# LED Pin setup
GPIO.setup(yled, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(rled, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(gled, GPIO.OUT, initial=GPIO.LOW)

# Wake Up Roomba Sequence
GPIO.output(gled, GPIO.HIGH) # Turn on green LED to say we are alive
print(" Starting ROOMBA... ")
Roomba = RoombaCI_lib.Create_2("/dev/ttyS0", 115200)
Roomba.ddPin = 23 # Set Roomba dd pin number
GPIO.setup(Roomba.ddPin, GPIO.OUT, initial=GPIO.LOW)
Roomba.WakeUp(131) # Start up Roomba in Safe Mode
# 131 = Safe Mode; 132 = Full Mode (Be ready to catch it!)
Roomba.BlinkCleanLight() # Blink the Clean light on Roomba

if Roomba.Available() > 0: # If anything is in the Roomba receive buffer
	x = Roomba.DirectRead(Roomba.Available()) # Clear out Roomba boot-up info
	#print(x) # Include for debugging

print(" ROOMBA Setup Complete")
GPIO.output(yled, GPIO.HIGH) # Indicate within setup sequence
# Initialize IMU
print(" Starting IMU...")
imu = RoombaCI_lib.LSM9DS1_IMU() # Initialize IMU
time.sleep(0.5)
# Calibrate IMU
print(" Calibrating IMU...")
Roomba.Move(0,75) # Start Roomba spinning
imu.CalibrateMag() # Calculate magnetometer offset values
Roomba.Move(0,0) # Stop Roomba spinning
time.sleep(0.5)
imu.CalibrateAccelGyro() # Calculate accelerometer and gyroscope offset values
# Display offset values
print("mx_offset = {:f}; my_offset = {:f}; mz_offset = {:f}".format(imu.mx_offset, imu.my_offset, imu.mz_offset))
print("ax_offset = {:f}; ay_offset = {:f}; az_offset = {:f}".format(imu.ax_offset, imu.ay_offset, imu.az_offset))
print("gx_offset = {:f}; gy_offset = {:f}; gz_offset = {:f}".format(imu.gx_offset, imu.gy_offset, imu.gz_offset))
print(" IMU Setup Complete")
time.sleep(1) # Gives time to read offset values before continuing
GPIO.output(yled, GPIO.LOW) # Indicate setup sequence is complete

if Xbee.inWaiting() > 0: # If anything is in the Xbee receive buffer
	x = Xbee.read(Xbee.inWaiting()).decode() # Clear out Xbee input buffer
	#print(x) # Include for debugging

# Main Code #
# Get initial angle from IMU
angle = imu.CalculateHeading()
#input the speed
spnspd = 100
speed_step = 20

#times, spin time is from formula
spinTime = (WHEEL_SEPARATION * math.pi) / (4 * spnspd)
backTime = 0.5
#initializes timers
moveHelper = (time.time() - (spinTime + backTime))
query_timer = 0.015625 # Time base for Roomba query

# Read in initial wheel count values from Roomba
Roomba.SendQuery(7,43,44,42,41,45)
while Roomba.Available() == 0:
	pass # Wait for sensor packet values to be returned
bumper_byte, l_counts_current, r_counts_current, l_speed, r_speed, light_bumper = Roomba.ReadQuery(7, 43, 44, 42, 41, 45) # Read new wheel counts

while True:
	try:
		distance = 0.0 # initial distance travelled (millimeters)
		x_pos = 0.0 # initial x-direction position (millimeters)
		y_pos = 0.0 # initial y-direction position (millimeters)
		forward_value = 0 # Initial forward speed (millimeters/second)
		# Print current angle of Roomba
		print("Angle: {:f}".format(angle))
		# Request for the desired angle to turn to
		desired_heading = float(input("Angle? "))

		data_time = 0.0 # 0 seconds initial
		# Start Query Data Stream
		#Roomba.StartQueryStream(7,43,44,42,41,45)

		# Determine initial spin speed value for Roomba
		spin_value = DHTurn(angle, desired_heading, epsilon)
		# Restart base timers
		base = time.time()
		query_base = time.time()

		while spin_value != 0: # If the Roomba needs to turn...
			try:
				if (time.time() - query_base) > query_timer:
					Roomba.SendQuery(7,43,44,42,41,45)
					query_base += query_timer

				if Roomba.Available() > 0:
					# Record the current time since the beginning of loop
					data_time = time.time() - base

					bumper_byte, l_counts, r_counts, l_speed, r_speed, light_bumper = Roomba.ReadQuery(7,43,44,42,41,45) # Read new wheel counts
					[mx,my,mz] = imu.ReadMag() # Read magnetometer component values
					#imu_angle = imu.CalculateHeading() # Calculate heading
					# Note: imu_angle may not correspond to mx, my, mz
					[ax,ay,az] = imu.ReadAccel() # Read accelerometer component values
					[gx,gy,gz] = imu.ReadGyro() # Read gyroscope component values

					# Calculate the count differences and correct for overflow
					delta_l_count = (l_counts - l_counts_current)
					if delta_l_count > pow(2,15): # 2^15 is somewhat arbitrary
						delta_l_count -= pow(2,16)
					if delta_l_count < -pow(2,15): # 2^15 is somewhat arbitrary
						delta_l_count += pow(2,16)
					delta_r_count = (r_counts - r_counts_current)
					if delta_r_count > pow(2,15): # 2^15 is somewhat arbitrary
						delta_r_count -= pow(2,16)
					if delta_r_count < -pow(2,15): # 2^15 is somewhat arbitrary
						delta_r_count += pow(2,16)
					# Calculated the forward distance traveled since the last counts
					distance_change = DISTANCE_CONSTANT * (delta_l_count + delta_r_count) * 0.5
					# Calculated the turn angle change since the last counts
					angle_change = TURN_CONSTANT * (delta_l_count - delta_r_count)
					distance += distance_change # Updated distance of Roomba
					angle += angle_change # Update angle of Roomba and correct for overflow
					if angle >= 360 or angle < 0:
						angle = (angle % 360) # Normalize the angle value from [0,360)
					# Calculate position data
					delta_x_pos = distance_change * math.cos(math.radians(angle))
					delta_y_pos = distance_change * math.sin(math.radians(angle))
					x_pos += delta_x_pos
					y_pos += delta_y_pos

					spin_value = DHTurn(angle, desired_heading, epsilon) # Determine the spin speed to turn toward the desired heading

					'''# Increment spin movement speed toward the set speed
					if spin_value < set_spin_value: # If it is less than the set speed...
						spin_value += speed_step # Increment the speed by a step
						if spin_value > set_spin_value: # If the speed went to far...
							spin_value = set_spin_value # Set it to the set speed
					if spin_value > set_spin_value: # If it is more than the set speed...
						spin_value -= speed_step # Decrement the speed by a step
						if spin_value < set_spin_value: # If the speed went to far...
							spin_value = set_spin_value # Set it to the set speed
					'''
					# Print out pertinent data values
					#print("{0:.5f}, {1:.3f}, {2:.3f}, {3:.3f}, {4:.3f}, {5:0>8b}, {6:0>8b}, {7}, {8};".format(data_time,desired_heading,angle,y_pos,x_pos,bumper_byte,light_bumper,l_counts,r_counts))
					print("{0:.5f}, {1:.5f}, {2:.5f}, {3:.5f}, {4:.5f}, {5:.5f}, {6:.5f}, {7:.5f}, {8:.5f}, {9:.5f};".format(data_time,mx,my,mz,ax,ay,az,gx,gy,gz))

					Roomba.Move(forward_value, spin_value) # Spin the Roomba toward the desired heading

					# Update current wheel encoder counts
					l_counts_current = l_counts
					r_counts_current = r_counts

			except KeyboardInterrupt:
				break

		forward_value = 0 # initial forward speed value (mm/s)
		spin_value = 0 # initial spin speed value (mm/s)
		Roomba.Move(forward_value, spin_value) # Stop Roomba movement
		'''Roomba.PauseQueryStream()
		if Roomba.Available() > 0:
			x = Roomba.DirectRead(Roomba.Available()) # Clear out residual Roomba data
			#print(x) # Include for debugging purposes
		'''
		distance = 0.0 # reset initial distance travelled
		# Request amount of distance to travel
		desired_distance = float(input("Distance? ")) # in millimeters
		# Request amount of speed to travel
		forward_value = int(input("Speed? ")) # in millimeters per second

		#Roomba.ResumeQueryStream()
		# Restart base timers
		base = time.time()
		query_base = time.time()

		while distance < desired_distance: # Until we have reached the desired_distance...
			try:
				#print("Testing 2nd Loop")
				if (time.time() - query_base) > query_timer:
					Roomba.SendQuery(7,43,44,42,41,45)
					query_base += query_timer

				if Roomba.Available() > 0:
					# Record the current time since the beginning of loop
					data_time = time.time() - base

					bumper_byte, l_counts, r_counts, l_speed, r_speed, light_bumper = Roomba.ReadQuery(7,43,44,42,41,45) # Read new wheel counts
					[mx,my,mz] = imu.ReadMag() # Read magnetometer component values
					#imu_angle = imu.CalculateHeading() # Calculate heading
					# Note: imu_angle may not correspond to mx, my, mz
					[ax,ay,az] = imu.ReadAccel() # Read accelerometer component values
					[gx,gy,gz] = imu.ReadGyro() # Read gyroscope component values

					# Calculate the count differences and correct for overflow
					delta_l_count = (l_counts - l_counts_current)
					if delta_l_count > pow(2,15): # 2^15 is somewhat arbitrary
						delta_l_count -= pow(2,16)
					if delta_l_count < -pow(2,15): # 2^15 is somewhat arbitrary
						delta_l_count += pow(2,16)
					delta_r_count = (r_counts - r_counts_current)
					if delta_r_count > pow(2,15): # 2^15 is somewhat arbitrary
						delta_r_count -= pow(2,16)
					if delta_r_count < -pow(2,15): # 2^15 is somewhat arbitrary
						delta_r_count += pow(2,16)
					# Calculated the forward distance traveled since the last counts
					distance_change = DISTANCE_CONSTANT * (delta_l_count + delta_r_count) * 0.5
					# Calculated the turn angle change since the last counts
					angle_change = TURN_CONSTANT * (delta_l_count - delta_r_count)
					distance += distance_change # Updated distance of Roomba
					angle += angle_change # Update angle of Roomba and correct for overflow
					if angle >= 360 or angle < 0:
						angle = (angle % 360) # Normalize the angle value from [0,360)
					# Calculate position data
					delta_x_pos = distance_change * math.cos(math.radians(angle))
					delta_y_pos = distance_change * math.sin(math.radians(angle))
					x_pos += delta_x_pos
					y_pos += delta_y_pos

					spin_value = DHTurn(angle, desired_heading, epsilon) # Determine the spin speed to turn toward the desired heading

					'''# Increment forward movement speed toward the set speed
					if forward_value < set_forward_value: # If it is less than the set speed...
						forward_value += speed_step # Increment the speed by a step
						if forward_value > set_forward_value: # If the speed went to far...
							forward_value = set_forward_value # Set it to the set speed
					if forward_value > set_forward_value: # If it is more than the set speed...
						forward_value -= speed_step # Decrement the speed by a step
						if forward_value < set_forward_value: # If the speed went to far...
							forward_value = set_forward_value # Set it to the set speed
					# Increment spin movement speed toward the set speed
					if spin_value < set_spin_value: # If it is less than the set speed...
						spin_value += speed_step # Increment the speed by a step
						if spin_value > set_spin_value: # If the speed went to far...
							spin_value = set_spin_value # Set it to the set speed
					if spin_value > set_spin_value: # If it is more than the set speed...
						spin_value -= speed_step # Decrement the speed by a step
						if spin_value < set_spin_value: # If the speed went to far...
							spin_value = set_spin_value # Set it to the set speed
					'''
					# Print out pertinent data values
					#print("{0:.5f}, {1:.3f}, {2:.3f}, {3:.3f}, {4:.3f}, {5:0>8b}, {6:0>8b}, {7}, {8};".format(data_time,desired_heading,angle,y_pos,x_pos,bumper_byte,light_bumper,l_counts,r_counts))
					print("{0:.5f}, {1:.5f}, {2:.5f}, {3:.5f}, {4:.5f}, {5:.5f}, {6:.5f}, {7:.5f}, {8:.5f}, {9:.5f};".format(data_time,mx,my,mz,ax,ay,az,gx,gy,gz))

					Roomba.Move(forward_value, spin_value) # Spin the Roomba toward the desired heading

					# Update current wheel encoder counts
					l_counts_current = l_counts
					r_counts_current = r_counts

			except KeyboardInterrupt:
				break # Break out of the loop early

		forward_value = 0 # initial forward speed value (mm/s)
		spin_value = 0 # initial spin speed value (mm/s)
		Roomba.Move(forward_value, spin_value) # Stop Roomba movement
		'''Roomba.PauseQueryStream()
		if Roomba.Available() > 0:
			x = Roomba.DirectRead(Roomba.Available()) # Clear out residual Roomba data
			#print(x) # Include for debugging purposes
		'''
	except KeyboardInterrupt:
		print("") # Move cursor down a line
		break # End the loop

## -- Ending Code Starts Here -- ##
# Make sure this code runs to end the program cleanly
GPIO.output(gled, GPIO.LOW) # Turn off green LED

Roomba.ShutDown() # Shutdown Roomba serial connection
Xbee.close()
GPIO.cleanup() # Reset GPIO pins for next program
