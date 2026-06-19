This is a Streamlit application for visualizing BlueBikes data!

## Development

To start quickly, run `make setup`.

### Layer Dependencies

This project uses layered architecture with a strict dependency direction.

ui → schemas → service → domain
                      ↓
                    repo → db

### Commits

This project uses [Conventional Commits](https://www.conventionalcommits.org/) enforced by [commitizen](https://commitizen-tools.github.io/commitizen/). Run `make commit` to stage all files and commit, or `uv run cz c`. Scopes mirror the layers described above.

