def main():
    try:
        from pageserve.cli._commands import cli
    except ImportError:
        raise ImportError("CLI cần cài thêm:\n    pip install 'pageserve[cli]'")
    cli()
