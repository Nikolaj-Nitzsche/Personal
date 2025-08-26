import TimeTagger
from time import sleep

TIMETAGGER_DEVICE_ID="2223001159"

tagger = TimeTagger.createTimeTagger(serial=TIMETAGGER_DEVICE_ID)
#connect to the Time Tagger via USB

tagger.startServer(access_mode = TimeTagger.AccessMode.Control,port=41101)
# Start the Server. TimeTagger.AccessMode sets the access rights for clients. Port defines the network port to be used
# The server keeps running until the command tagger.stopServer() is called or until the program is terminated``
while(True):
    sleep(100)