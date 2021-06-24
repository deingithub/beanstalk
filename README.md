# beanstalk

beanstalk allows you and some friends to access some functions of the computer it's running on remotely.

## features

 * play audio or video using youtube-dl
 * use google TTS to say silly things to you
 * see what your MPRIS-enabled music player is playing right now
 * make and upload screenshots
 * make and upload short gifs using your webcam

apart from these *gravely privacy-violating nonsense antifeatures* it also has some *completely misplaced actual features* like:

 * grabbing a random file from a configured folder and uploading it
 * running SQL statements against a public database
 * providing your friends with parcel tracking updates for some german shipping companies

as far as possible within this utterly nightmarish basic premise, it tries to help you limit the total loss of privacy while doing that by:

 * awaiting manual confirmation before uploading anything likely to be sensitive (screenshots, webcam)
 * allowing you to manually disable any set of functions from the first set until the bot restarts
 * uploading to a configured special channel and linking that upload in the actual channel instead of directly uploading it to allow you to delete media (from continued public visibility there, at least) even after you lose access to the channel the bot is being used in
 * "killfile" for individual users you find annoying
 * all commands work only in the bot's DMs with yourself or in approved guilds

## compatibility
beanstalk is very much tailored to my current setup (GNOME on NixOS Linux), for example taking screenshots will only work if you use the GNOME shell. beyond that it though should be …fairly portable — if you have Nix and you also remove all the references to my name from it, unless you also happen to be named Cass, in which case, congratulations on having a good name.

## license
all rites reversed
