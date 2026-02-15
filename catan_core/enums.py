from enum import Enum


class ResourceType(str, Enum):
    TIMBER = "Timber"
    STONE = "Stone"
    MEAT = "Meat"
    GRAIN = "Grain"
    IRON = "Iron"
    WASTELAND = "Wasteland"


class DevelopmentCardType(str, Enum):
    KNIGHT = "Knight"
    VICTORY_POINT = "Victory Point"
    ROAD_BUILDING = "Road Building"
    YEAR_OF_PLENTY = "Year of Plenty"
    MONOPOLY = "Monopoly"
