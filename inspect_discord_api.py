import discord
import inspect
import discord.app_commands as ac

print('version', discord.__version__)
print('clear_commands', inspect.signature(ac.CommandTree.clear_commands))
print('sync', inspect.signature(ac.CommandTree.sync))
print('clear_commands obj', ac.CommandTree.clear_commands)
print('sync obj', ac.CommandTree.sync)
