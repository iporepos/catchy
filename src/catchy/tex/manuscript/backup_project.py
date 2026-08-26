from losalamos.project import publish
from pathlib import Path

PROJECT_PATH = Path(__file__).parent.parent.parent

def main():

    publish(
        sources=[PROJECT_PATH],
        name="catchy-tex",
        folder="C:/Users/Ipo/My Drive/athens/losalamos/B000/B005/outputs",
    )

    publish(
        sources=[PROJECT_PATH / "src/published"],
        name="manuscript-v202601",
        folder="C:/Users/Ipo/My Drive/athens/losalamos/B000/B005/outputs",
    )

    publish(
        sources=[PROJECT_PATH / "src/overleaf_zips"],
        name="manuscript-overleaf",
        folder="C:/Users/Ipo/My Drive/athens/losalamos/B000/B005/outputs",
    )

if __name__ == '__main__':
    print(PROJECT_PATH)
    main()