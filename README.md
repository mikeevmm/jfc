# Journal Fabulous Club

`jfc` is an utility to make reviewing ArXiv papers for your Journal Club easier.

## Install

```bash
git clone git@github.com:mikeevmm/jfc.git
cd jfc
bash install.sh
```

## How to Use

`jfc` aggregates unseen articles from the specified timeframe (see the
[configuration](##configuration) section), and displays them to you in an
interactive prompt. From the title, you can choose to read the abstract, and
from there you can choose to open the ArXiv PDF.

Run `jfc` to get an interactive prompt.

## Configuration

`jfc` has some configuration parameters, which are set in the [TOML][TOML] file
that lives in the installation directory.

Running `jfc config` will output the full directory of the configuration
directory. Since most editors accept a path as an argument for the file to open,
this means you can quickly edit the configuration (in bash) with

```bash
<your favourite editor> $(jfc config)
```

### Parameters

 * `span` --- The timeframe of publication dates to aggregate, in days, and
    counting backwards from today. [Default: 7]

[TOML]: https://en.wikipedia.org/wiki/TOML
