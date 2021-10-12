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

 * `span` The timeframe of publication dates to aggregate, in days, and
    counting backwards from today. [Default: 7]

## Licence

`jfc` is licenced under a GNU General Public License, version 3. This
[**informally**][GPLv3] means that:

> You may copy, distribute and modify the software as long as you track
> changes/dates in source files. Any modifications to or software including
> (via compiler) GPL-licensed code must also be made available under the GPL
> along with build & install instructions.

You can find a copy of the licence under `LICENCE`.

[TOML]: https://en.wikipedia.org/wiki/TOML
[GPLv3]: https://tldrlegal.com/license/gnu-lesser-general-public-license-v2.1-(lgpl-2.1)
