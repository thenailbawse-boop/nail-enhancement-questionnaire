-- Content Made Easy: opens the editor in its own window, and turns it on first if it is off.
-- Made on the member's own Mac by the contentmadeeasy skill with osacompile. Never posts, sends or deletes anything.
try
	do shell script "F=$(cat \"$HOME/.contentmadeeasy-folder\" 2>/dev/null || echo \"$HOME/Content-Made-Easy\"); /bin/zsh \"$F/open-app.sh\""
on error errMsg
	display dialog "Content Made Easy didn't open." & return & return & errMsg & return & return & "Open Claude and type /contentmadeeasy to fix it." buttons {"OK"} default button 1 with title "Content Made Easy"
end try
