-- Content Made Easy Start: turns the editor on when the computer starts, without opening a window, so a bookmark always works.
-- Added to Login Items by the contentmadeeasy skill, only when the member says yes. Never posts, sends or deletes anything.
try
	do shell script "F=$(cat \"$HOME/.contentmadeeasy-folder\" 2>/dev/null || echo \"$HOME/Content-Made-Easy\"); CME_NOOPEN=1 /bin/zsh \"$F/open-app.sh\""
end try
