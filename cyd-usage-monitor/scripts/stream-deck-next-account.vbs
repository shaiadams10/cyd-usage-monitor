Option Explicit

Dim fileSystem, shell, scriptDirectory, powerShellScript, command

Set fileSystem = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
powerShellScript = fileSystem.BuildPath(scriptDirectory, "stream-deck-next-account.ps1")
command = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File " _
    & Chr(34) & powerShellScript & Chr(34)

' Window style 0 launches PowerShell without creating a visible console.
shell.Run command, 0, False
