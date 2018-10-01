''' Roomba_PRCSync.py
Purpose: Synchronize heading of Roomba network using PCO model
	Uses PRC function to synchronize (from Energy-Efficient Sync, Wang, 2012)
	Uses Roomba wheel encoders to update heading value over time.
IMPORTANT: Must be run using Python 3 (python3)
Last Modified: 7/12/2018
'''
## Import libraries ##
import serial
import time
import RPi.GPIO as GPIO
import math
import RoombaCI_lib # Make sure this file is in the same directory
from RoombaCI_lib import DHTurn

## Variables and Constants ##
global Xbee # Specifies connection to Xbee
Xbee = serial.Serial('/dev/ttyUSB0', 115200) # Baud rate should be 115200
Nodes = 6 # Number of Roombas Running

# LED pin numbers
yled = 5
rled = 6
gled = 13

# Pulse definitions
reset_pulse = "b" # Rest pulse character
sync_pulse = "a" # Sync pulse character

# Timing Counter Parameters
data_timer = 0.05
reset_timer = 300

# Counter Parameters
cycle_threshold = 360.0 # Threshold for phase of PCO
cycle_time = 5.0 # Length of PCO cycle in seconds

# Counter Constants
counter_adjust = cycle_time # Amount of counter adjustment per cycle
counter_ratio = (cycle_threshold)/(cycle_time) # Fraction of phase cycle completed in one second

# Synchronization Parameters
global angle # Heading of Roomba (found from magnetometer)
global counter # Counter of Roomba (works with angle to compute "phase")
coupling_ratio = 0.5 # Ratio for amount to turn - in range (0, 1]
epsilon = 0.5 # (Ideally) smallest resolution of magnetometer
global desired_heading  # Heading set point for Roomba

refr_period = 0.0*cycle_threshold # Refractory period for PRC

# Roomba Navigation Constants
WHEEL_DIAMETER = 72 # millimeters
WHEEL_SEPARATION = 235 # millimeters
WHEEL_COUNTS = 508.8 # counts per revolution
DISTANCE_CONSTANT = (WHEEL_DIAMETER * math.pi)/(WHEEL_COUNTS) # millimeters/count
TURN_CONSTANT = (WHEEL_DIAMETER * 180)/(WHEEL_COUNTS * WHEEL_SEPARATION) # degrees/count

## Functions and Definitions ##
''' Sends sync_pulse to Xbee
	Used to signal when phase equals 360 degrees '''
def SendSyncPulse():
	global sync_pulse
	global gled
	#print("Sync Pulse Sent") # Include for debugging
	GPIO.output(gled, GPIO.HIGH) # Tells me I'm sending a pulse
	Xbee.write(sync_pulse.encode()) # Send pulse over Xbee
	GPIO.output(gled, GPIO.LOW)  # Tells me I'm done sending a pulse

''' Sends reset_pulse to Xbee
	Used to signal when to new node joins network '''
def SendResetPulse():
	global reset_pulse
	global gled
	global rled
	#print("Reset Pulse Sent") # Include for debugging
	GPIO.output(gled, GPIO.HIGH) # Tells me I'm sending a pulse
	GPIO.output(rled, GPIO.HIGH)
	Xbee.write(reset_pulse.encode()) # Send pulse over Xbee
	GPIO.output(gled, GPIO.LOW)  # Tells me I'm done sending a pulse
	GPIO.output(rled, GPIO.LOW)

''' Receives pulse from Xbee and returns the value
	'''
def ReceivePulse():
	if Xbee.inWaiting() > 0:
		message = Xbee.read(1).decode() # Read in one data
		#print("Received:", message) # Include for debugging
		return message # Return the data read.
	else:
		return '' # Return empty string

''' Reset all of the time-based counters
	Used when restarting synchronization'''
def ResetCounters():
	global counter_base
	global data_base
	global reset_base
	global counter
	global data_counter
	global angle
	global desired_heading
	counter_base = time.time() # Initialize counter
	data_base = time.time() # Initialize data timer
	reset_base = time.time() # Initialize reset timer
	counter = 0 # Reset phase counter
	data_counter = 0 # Reset data point counter
	angle = imu.CalculateHeading() # Reset initial angle value
	desired_heading = angle # Set to initial angle value

''' Returns necessary change in heading when a sync_pulse is received
	For standard delay-advance phase response function with refractory period
	'''
def PRCSync(phase):
	global cycle_threshold
	global refr_period
	global rled
	global epsilon
	if phase > refr_period: # If phase is greater than the refractory period...
		if phase > (cycle_threshold - epsilon):
			angle_change = 0 # No change in heading
			GPIO.output(rled, GPIO.HIGH) # Indicate sync pulse received, but no turning
		elif phase > 0.5*(cycle_threshold):
			angle_change = (cycle_threshold - phase) # Increase heading
			GPIO.output(rled, GPIO.LOW) # Indicate sync pulse received caused turn
		elif phase > epsilon:
			angle_change = (-1) * phase # Decrease heading
			GPIO.output(rled, GPIO.LOW) # Indicate sync pulse received caused turn
		else:
			angle_change = 0 # No change in heading
			GPIO.output(rled, GPIO.HIGH) # Indicate sync pulse received, but no turning
	else:
		angle_change = 0 # No change in heading
	return angle_change

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

# Open a text file for data retrieval
file_name = input("Name for data file: ")
file_name += ".txt"
datafile = open(file_name, "w") # Open a text file for storing data
	# Will overwrite anything that was in the text file previously

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
	print(x) # Include for debugging

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

forward = 0
# Read in initial wheel count values from Roomba
bumper_byte, l_counts_current, r_counts_current, light_bumper = Roomba.Query(7,43,44,45) # Read new wheel counts
# Initialize Synchronization
angle = 3*360/Nodes # Get initial heading information  *Note, this is where I would set the angle to a hard coded value. Upload different for each bot.

# Print out data header values
print("Data Counter, Data Time, Angle, Counter, Left Encoder Counts, Right Encoder Counts;")
# Write data values to a text file
datafile.write("Data Counter, Data Time, Angle, Counter, Left Encoder Counts, Right Encoder Counts;\n")

# Ready to begin PRCSync Loop
SendResetPulse() # Send reset pulse
ResetCounters() # Reset counter values
# Request data packets from Roomba (Stream)
Roomba.StartQueryStream(7,43,44,45) # Start query stream with specific sensor packets

while True:
	try:
		# Read query stream for specific packets (ReadQueryStream)
		if Roomba.Available() > 0: # If data has come in from the Roomba...
			data_time = time.time() - reset_base
			# Read in the data from the Stream
			bumper_byte, l_counts, r_counts, light_bumper = Roomba.ReadQueryStream(7,43,44,45)
			
			# Get needed data using the encoder counts (copied from "Roomba_Encoder_Test4.py")
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
			# Calculate the turn angle change since the last counts
			angle_change = TURN_CONSTANT * (delta_l_count - delta_r_count)
			angle += angle_change # Update angle of Roomba and correct for overflow
			if angle >= cycle_threshold:
				angle -= cycle_threshold
				counter_base -= counter_adjust
			elif angle < 0:
				angle += cycle_threshold
				counter_base += counter_adjust
			
			
			
			# Update current wheel encoder counts
			l_counts_current = l_counts
			r_counts_current = r_counts
			
		# Set counter value
	counter = (time.time() - counter_base)*counter_ratio
		# Send sync_pulse
	if (angle + counter) > cycle_threshold: # If (angle + counter) is greater than 360 degrees...
			SendSyncPulse()
			counter_base += counter_adjust
			
			# Receive pulse
		message = ReceivePulse()
			
		if message == reset_pulse: 
			#print("Reset Pulse Received.") # Include for debugging
			GPIO.output(gled, GPIO.HIGH) # Notify that reset_pulse received
			GPIO.output(rled, GPIO.HIGH)
			datafile.close() # Close the file to reset the data in it.
			ResetCounters() # Reset counters
			datafile = open(file_name, "w") # Open a text file for storing data
				# Will overwrite anything that was in the text file previously
			# Write data values to a text file
			datafile.write("Data Counter, Data Time, Angle, Counter, Left Encoder Counts, Right Encoder Counts;\n")
			GPIO.output(gled, GPIO.LOW)  # End notify that reset_pulse received
			GPIO.output(rled, GPIO.LOW)
		elif message == sync_pulse:
			#print("Sync Pulse Received.") # Include for debugging
			d_angle = PRCSync(angle + counter) # Calculate desired change in heading
			desired_heading = angle + (d_angle * coupling_ratio) # Update desired heading
			# Normalize desired_heading to range [0,360)
			if desired_heading >= cycle_threshold or desired_heading < 0:
				desired_heading = (desired_heading % cycle_threshold)
		if Roomba.Available() > 0: # If anything is in the Roomba receive buffer
			x = Roomba.DirectRead(Roomba.Available()) # Clear out Roomba boot-up info
				#print(x) # Include for debugging
			
		spin = DHTurn(angle, desired_heading, epsilon) # Value needed to turn to desired heading point
		Roomba.Move(forward, spin) # Move Roomba to desired heading point
			
		if spin == 0:
			GPIO.output(yled, GPIO.LOW) # Indicate Roomba is not turning
		else:
			GPIO.output(yled, GPIO.HIGH) # Indicate Roomba is turning
		
		# End "if Roomba.Available() > 0:
		# Print heading data to monitor every second
		if (time.time() - data_base) > data_timer: # After one second
			# Print data to monitor
			print("{0}, {1:.6f}, {2:.3f}, {3:.3f}, {4}, {5};".format(data_counter, data_time, angle, counter, l_counts, r_counts))
			# Write data values to a text file
			datafile.write("{0}, {1:.6f}, {2:.3f}, {3:.3f}, {4}, {5};\n".format(data_counter, data_time, angle, counter, l_counts, r_counts))
			
			data_counter += 1 # Increment counter for the next data sample
			data_base += data_timer
		
		# Reset counters of all Roombas after 5 minutes
		if (time.time() - reset_base) >= reset_timer: # After 5 minutes
			SendResetPulse() # Send reset_pulse
			# Reset all counters
			ResetCounters()
		
	except KeyboardInterrupt:
		print('') # Print new line
		break # Exit while loop

Roomba.PauseQueryStream()
time.sleep(0.1)
if Roomba.Available() > 0:
	x = Roomba.DirectRead(Roomba.Available()) # Clear out residual Roomba data
	#print(x) # Include for debugging purposes
Roomba.Move(0,0) # Stop Roomba movement

## -- Ending Code Starts Here -- ##
# Make sure this code runs to end the program cleanly
Roomba.PlaySMB()
datafile.close()
GPIO.output(gled, GPIO.LOW) # Turn off green LED

Roomba.ShutDown() # Shutdown Roomba serial connection
Xbee.close()
GPIO.cleanup() # Reset GPIO pins for next program
