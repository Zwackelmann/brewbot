 - install python

```bash
sudo apt-get update
sudo apt-get install -y build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev curl llvm \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  libffi-dev liblzma-dev git
```

 - install pyenv

```bash
curl https://pyenv.run | bash

# Add to .bashrc or .zshrc
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
```

 - restart shell and install python

```bash
pyenv install 3.12.11
pyenv global 3.12.11
```

 - copy files to respective paths

 - activate network service with

```bash
sudo systemctl enable systemd-networkd
sudo systemctl start systemd-networkd
```

 - activate user service with

```bash
systemctl --user daemon-reexec
systemctl --user daemon-reload
systemctl --user restart brewbot
```