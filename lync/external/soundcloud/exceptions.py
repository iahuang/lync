class SoundcloudException(Exception):
    pass

class SoundcloudClientIDException(SoundcloudException):
    pass

class SoundcloudSearchException(SoundcloudException):
    pass

class SoundcloudAudioDLException(SoundcloudException):
    pass