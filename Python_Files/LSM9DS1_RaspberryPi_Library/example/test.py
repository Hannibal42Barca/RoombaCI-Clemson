from ctypes import *
import time
from math import atan2

path = "/home/pi/RoombaCI/LSM9DS1_RaspberryPi_Library-master/lib/liblsm9ds1cwrapper.so"
lib = cdll.LoadLibrary(path)

lib.lsm9ds1_create.argtypes = []
lib.lsm9ds1_create.restype = c_void_p

lib.lsm9ds1_begin.argtypes = [c_void_p]
lib.lsm9ds1_begin.restype = None

lib.lsm9ds1_calibrate.argtypes = [c_void_p]
lib.lsm9ds1_calibrate.restype = None

lib.lsm9ds1_magAvailable.argtypes = [c_void_p]
lib.lsm9ds1_magAvailable.restype = c_int

lib.lsm9ds1_readMag.argtypes = [c_void_p]
lib.lsm9ds1_readMag.restype = c_int

lib.lsm9ds1_getMagX.argtypes = [c_void_p]
lib.lsm9ds1_getMagX.restype = c_float
lib.lsm9ds1_getMagY.argtypes = [c_void_p]
lib.lsm9ds1_getMagY.restype = c_float
lib.lsm9ds1_getMagZ.argtypes = [c_void_p]
lib.lsm9ds1_getMagZ.restype = c_float

lib.lsm9ds1_calcMag.argtypes = [c_void_p, c_float]
lib.lsm9ds1_calcMag.restype = c_float





imu = lib.lsm9ds1_create()
lib.lsm9ds1_begin(imu)

if lib.lsm9ds1_begin(imu) == 0:
    print("Failed to communicate with LSM9DS1.")
    quit()
lib.lsm9ds1_calibrate(imu)

x = []
y = []
z = []

for i in range(0,999):
    while lib.lsm9ds1_magAvailable(imu) == 0:
        pass
    lib.lsm9ds1_readMag(imu)

    mx = lib.lsm9ds1_getMagX(imu)
    my = lib.lsm9ds1_getMagY(imu)
    mz = lib.lsm9ds1_getMagZ(imu)

    cmx = lib.lsm9ds1_calcMag(imu, mx)
    cmy = lib.lsm9ds1_calcMag(imu, my)
    cmz = lib.lsm9ds1_calcMag(imu, mz)

    print (cmx)
    print (cmy)
    print (cmz)

    x.append(cmx)
    y.append(cmy)
    z.append(cmz)

    '''print("Angle - %f" % (180/3.14*atan2(cmy,cmx)))'''

print(x)

for i in range(0,999):
   print(x[i], end='')
   print(",", end='')
   print(y[i], end='')
   print(",", end='')
   print(z[i], end='')
   print(",")
