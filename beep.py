import pygame


def do_beep():
    pygame.mixer.init()
    pygame.mixer.music.load("alert_log.mp3")
    pygame.mixer.music.play()
