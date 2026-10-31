echo Made By D-Kaiser
echo QQ:3936198161
echo Email:先空着......
sleep 1

#换清华源
sed -i 's@^\(deb.*stable main\)$@#\1\ndeb https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main stable main@' $PREFIX/etc/apt/sources.list
echo -e "\033[31m换清华源成功"
sleep 1
apt update && apt upgrade
pkg update && pkg upgrade
echo -e "\033[31m包更新成功"
sleep 1
#安装pkg包
#pkg install mpv ffplay ffmpeg python curl git wget yt-dlp mc tmux termux-api tree zip p7zip rar tar -y
apt update
apt install mpv -y
apt install ffplay -y
apt install ffmpeg -y
apt install vlc -y
apt install python -y
apt install curl -y
apt install git -y
apt install wget -y
apt install aria2 -y
apt install yt-dlp -y
apt install mc -y
apt install tmux -y
apt install termux-api -y
apt install tree -y
apt install zip -y
apt install p7zip -y
apt install tar -y
apt install rar -y
apt install proot -y
apt install neofetch -y
apt install screenfetch -y
pkg install fzf -y
#安装有意思的pkg
pkg install cmatrix nyancat toilet cowsay sl catimg figlet -y
echo -e "\033[31m脚本结束"