"""A central place for defining FFmpeg audio filter chains."""

FFMPEG_FILTER_CHAINS = {
    "bassboost": "bass=g=15,dynaudnorm=f=200",
    "nightcore": "atempo=1.3,asetrate=44100*1.3,bass=g=5",
    "slowed": "atempo=0.85",  # Just slowed, no reverb
    "8d": "apulsator=hz=0.2",  # 8D audio effect
    "overdrive": "volume=15dB,acompressor=threshold=0.1:ratio=10:attack=0.003:release=0.1,volume=-5dB"  # Warm overdrive
}
