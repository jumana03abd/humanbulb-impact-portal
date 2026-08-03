from enum import IntEnum
import string
import random
class confidence(IntEnum):
    Not_At_All_Confident = 1
    Slightly_Confident = 2
    Very_Confident = 3
import csv
from enum import IntEnum

# Inherit from IntEnum so numeric comparison (<, >, ==) works directly
class Confidence(IntEnum):
    NOT_AT_ALL = 1
    SLIGHTLY = 2
    VERY = 3

def parseRating(val: str) -> int:
    """Parses a rating string into an integer value or Confidence enum integer."""
    val_clean = val.strip().lower()
    
    # Try direct integer conversion first
    try:
        return int(val_clean)
    except ValueError:
        pass
    
    # Text-based confidence parsing
    match val_clean:
        case "not at all" | "not at all confident" | "1":
            return Confidence.NOT_AT_ALL
        case "somewhat" | "slightly confident" | "2":
            return Confidence.SLIGHTLY
        case "very confident" | "very familiar" | "3":
            return Confidence.VERY
        case _:
            return 0  # Fallback for empty or unknown values
def randConf():
    rNum = random.randint(1,3)
    match rNum:
            case 1:
                return "not at all confident"
            case 2:
                return "slightly confident"
            case 3:
                return "very confident"
# def compare(rowList1, rowList2):
#     for i in range()