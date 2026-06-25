from src.app import AppConfig, LifelogApp


def main() -> None:
    app = LifelogApp(AppConfig())

    try:
        app.start()
        app.wait()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()


if __name__ == "__main__":
    main()
