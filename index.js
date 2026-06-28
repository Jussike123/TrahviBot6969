const fs = require('fs');
const path = require('path');
const axios = require('axios');
const { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder } = require('discord.js');
const ERLCClient = require('./erlcClient');

const configPath = path.join(__dirname, 'config.json');
if (!fs.existsSync(configPath)) {
  console.error('Missing config.json. Copy config.example.json to config.json and fill it in.');
  process.exit(1);
}

const config = require(configPath);
const { token, clientId, erlcApiBaseUrl, erlcApiKey, notifyDiscordId, notifyChannelId, guildId, boatApiBaseUrl, boatApiToken } = config;

if (!token || !clientId || !erlcApiBaseUrl || !erlcApiKey || !notifyDiscordId) {
  console.error('Invalid config.json. Ensure token, clientId, erlcApiBaseUrl, erlcApiKey, and notifyDiscordId are set.');
  process.exit(1);
}

if (guildId && guildId === clientId) {
  console.warn('Warning: guildId matches clientId. guildId must be your Discord server ID, not the bot client ID.');
}

const erlClient = new ERLCClient({ baseUrl: erlcApiBaseUrl, apiKey: erlcApiKey });
const client = new Client({ intents: [GatewayIntentBits.Guilds] });

const challengeDefinitions = {
  pauk: {
    displayName: 'Pauk',
    reward: 'Pauk',
    missions: [
      {
        id: 'pauk-1',
        name: 'Eddie ülevaatuspunkt',
        zip: '501',
        building: null,
        requiredStaySec: 90,
        description: 'Eddie location — stay 1.5 minutes'
      },
      {
        id: 'pauk-2',
        name: 'Hiina tänava draakoni pood',
        zip: '220',
        building: '2201',
        requiredStaySec: 60,
        description: 'Hiina tänava draakoni pood building 2201 — stay 1 minute'
      }
    ]
  },
  klaasilõikur: {
    displayName: 'Klaasilõikur',
    reward: 'Klaasilõikur',
    missions: [
      {
        id: 'klaasilõikur-1',
        name: 'Pärnu autoparandus',
        zip: '211',
        building: '2111',
        requiredStaySec: 60,
        description: 'Pärnu autoparandus building 2111 — stay 1 minute'
      },
      {
        id: 'klaasilõikur-2',
        name: 'Haapsalu autoparandus',
        zip: '1108',
        building: '11082',
        requiredStaySec: 120,
        description: 'Haapsalu autoparandus building 11082 — stay 2 minutes'
      }
    ]
  },
  lasercutter: {
    displayName: 'Laser cutter',
    reward: 'Laserlõikur',
    missions: [
      {
        id: 'lasercutter-1',
        name: 'Pärnu autoparandus',
        zip: '211',
        building: '2111',
        requiredStaySec: 180,
        description: 'Pärnu autoparandus building 2111 — stay 3 minutes'
      },
      {
        id: 'lasercutter-2',
        name: 'Haapsalu autoparandus',
        zip: '1108',
        building: '11082',
        requiredStaySec: 180,
        description: 'Haapsalu autoparandus building 11082 — stay 3 minutes'
      }
    ]
  }
};

const activeSessions = new Set();
const NOTIFY_CHANNEL_ID = notifyChannelId || '1040589270991241239';

function registerCommands() {
  const commands = [
    new SlashCommandBuilder()
      .setName('start')
      .setDescription('Start the Roblox arrival challenge')
      .addStringOption(option => option
        .setName('username')
        .setDescription('Roblox username')
        .setRequired(true)
      )
      .addStringOption(option => option
        .setName('challenge')
        .setDescription('Choose a challenge: pauk, klaasilõikur, lasercutter')
        .setRequired(true)
        .addChoices(
          { name: 'Pauk', value: 'pauk' },
          { name: 'Klaasilõikur', value: 'klaasilõikur' },
          { name: 'Laser cutter', value: 'lasercutter' }
        )
      )
      .addStringOption(option => option
        .setName('mission')
        .setDescription('Choose the exact mission to attempt')
        .setRequired(true)
        .addChoices(
          { name: 'Pauk #1: Eddie ülevaatuspunkt', value: 'pauk-1' },
          { name: 'Pauk #2: Hiina tänava draakoni pood', value: 'pauk-2' },
          { name: 'Klaasilõikur #1: Pärnu autoparandus', value: 'klaasilõikur-1' },
          { name: 'Klaasilõikur #2: Haapsalu autoparandus', value: 'klaasilõikur-2' },
          { name: 'Laser cutter #1: Pärnu autoparandus', value: 'lasercutter-1' },
          { name: 'Laser cutter #2: Haapsalu autoparandus', value: 'lasercutter-2' }
        )
      )
      .toJSON(),
    new SlashCommandBuilder()
      .setName('location')
      .setDescription('Get the current Roblox player location')
      .addStringOption(option => option
        .setName('username')
        .setDescription('Roblox username')
        .setRequired(true)
      )
      .toJSON(),
    new SlashCommandBuilder()
      .setName('hint')
      .setDescription('Send an in-game hint command')
      .addStringOption(option => option
        .setName('message')
        .setDescription('Hint text to send in game')
        .setRequired(true)
      )
      .toJSON(),
    new SlashCommandBuilder()
      .setName('kill')
      .setDescription('Send an in-game kill command')
      .addStringOption(option => option
        .setName('target')
        .setDescription('Target player or kill parameter (optional)')
        .setRequired(false)
      )
      .toJSON(),
    new SlashCommandBuilder()
      .setName('kill1')
      .setDescription('Kill all players within the defined area')
      .toJSON()
  ];

  const rest = new REST({ version: '10' }).setToken(token);
  if (guildId) {
    console.log(`Registering commands for guild ${guildId}`);
    return rest.put(Routes.applicationGuildCommands(clientId, guildId), { body: commands });
  }

  console.log('Registering global commands (may take up to an hour to update)');
  return rest.put(Routes.applicationCommands(clientId), { body: commands });
}

async function addBoatInventoryItem(discordId, itemName) {
  if (!boatApiBaseUrl || !boatApiToken) {
    return { error: 'UnbelivableBoat API credentials are not configured.' };
  }

  const apiBase = boatApiBaseUrl.replace(/\/+$/,'');
  const url = `${apiBase}/inventory/add`;
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${boatApiToken}`
  };

  try {
    const response = await axios.post(url, { discordId, item: itemName }, { headers, timeout: 5000 });
    return response.data;
  } catch (error) {
    return { error: error.response?.data || error.message || 'Boat inventory request failed.' };
  }
}

function normalizePostalCode(locationData) {
  if (!locationData || typeof locationData !== 'object') return null;

  const location = locationData.location || locationData;
  const postalCode = location.PostalCode || location.postalCode || location.zipCode || location.zip_code || location.zip;
  if (postalCode == null) return null;
  return String(postalCode).trim();
}

function normalizeBuildingNumber(locationData) {
  if (!locationData || typeof locationData !== 'object') return null;

  const location = locationData.location || locationData;
  const buildingNumber = location.BuildingNumber || location.buildingNumber || location.building_number || location.building;
  if (buildingNumber == null) return null;
  return String(buildingNumber).trim();
}

function locationMatches(locationData, target) {
  if (!locationData || typeof locationData !== 'object') return false;

  const postalCode = normalizePostalCode(locationData);
  if (!postalCode || !postalCode.startsWith(target.zip)) return false;

  if (target.building) {
    const buildingNumber = normalizeBuildingNumber(locationData);
    if (!buildingNumber || buildingNumber !== target.building) return false;
  }

  return true;
}

function formatLocationData(locationData) {
  if (!locationData) return 'Location data is not available.';
  if (locationData.error) return `API error: ${locationData.error}`;

  const location = locationData.location || {};
  const buildingNumber = location.BuildingNumber;
  const streetName = location.StreetName;
  const postalCode = location.PostalCode;
  const locationX = location.LocationX;
  const locationZ = location.LocationZ;

  const parts = [];
  if (buildingNumber && streetName) {
    parts.push(`${buildingNumber} ${streetName}`);
  } else if (streetName) {
    parts.push(streetName);
  }

  if (postalCode) {
    parts.push(`Postal code ${postalCode}`);
  }

  if (locationX != null && locationZ != null) {
    parts.push(`Coordinates: ${locationX}, ${locationZ}`);
  }

  return parts.length ? parts.join(' — ') : JSON.stringify(location, null, 2);
}

async function checkArrival(interaction, username, challenge, mission, discordId) {
  const notifyUserId = notifyDiscordId;
  const notifyUser = await client.users.fetch(notifyUserId).catch(() => null);

  const missionName = mission.name;
  const missionZip = mission.zip;
  const missionBuilding = mission.building;
  const requiredStayMs = mission.requiredStaySec * 1000;
  const arrivalDeadlineMs = 5 * 60 * 1000; // 5 minutes to start being in place
  const followUpDelayMs = 5000;

  const missionDescription = mission.description;
  await interaction.followUp({ content: `Challenge: ${challenge.displayName}
Go to ${missionName} (ZIP ${missionZip}${missionBuilding ? `, Building ${missionBuilding}` : ''}). ${missionDescription}. You have 5 minutes to arrive and stay in place.`, ephemeral: true });

  const startTime = Date.now();
  let arrivedAtTarget = false;
  let arrivalTime = null;

  while (Date.now() - startTime < arrivalDeadlineMs) {
    try {
      const locationData = await erlClient.getPlayerLocation(username);
      if (locationMatches(locationData, mission)) {
        arrivedAtTarget = true;
        arrivalTime = Date.now();
        break;
      }
    } catch (error) {
      console.warn('ERLC poll failed:', error.message || error);
    }

    await new Promise(resolve => setTimeout(resolve, 5000));
  }

  if (!arrivedAtTarget) {
    await interaction.followUp({ content: 'Failed: player did not reach the target location within 5 minutes.', ephemeral: true });
    if (notifyUser) {
      await notifyUser.send(`Challenge failed: ${challenge.displayName} mission not reached in time.`).catch(() => {});
    }
    return false;
  }

  await interaction.followUp({ content: `Player reached ${missionName}. Waiting for ${mission.requiredStaySec} seconds of continuous presence...`, ephemeral: true });

  const stayStart = Date.now();
  while (Date.now() - stayStart < requiredStayMs) {
    try {
      const locationData = await erlClient.getPlayerLocation(username);
      if (!locationMatches(locationData, mission)) {
        await interaction.followUp({ content: 'Player left the area before staying long enough. Challenge failed.', ephemeral: true });
        if (notifyUser) {
          await notifyUser.send(`Challenge failed: ${challenge.displayName} mission abandoned before stay time completed.`).catch(() => {});
        }
        return false;
      }
    } catch (error) {
      console.warn('ERLC poll failed during stay check:', error.message || error);
    }

    await new Promise(resolve => setTimeout(resolve, 5000));
  }

  try {
    await erlClient.sendGameHint(':h arrived');
  } catch (error) {
    console.warn('Could not send arrival hint:', error.message || error);
  }

  await new Promise(resolve => setTimeout(resolve, followUpDelayMs));

  try {
    const channel = await client.channels.fetch(NOTIFY_CHANNEL_ID);
    if (channel) {
      await channel.send(`<@${notifyDiscordId}> ${challenge.reward} task completed by ${username}!`);
    }
  } catch (error) {
    console.warn('Could not send channel ping:', error.message || error);
  }

  const boatResult = await addBoatInventoryItem(String(userId), challenge.reward);
  if (boatResult?.error) {
    console.warn('Boat inventory error:', boatResult.error);
  }

  const successMessage = boatResult?.error
    ? `Success! ${challenge.reward} completed, but boat inventory update failed.`
    : `Success! ${challenge.reward} awarded via UNBELIVABLEBOAT.`;

  if (notifyUser) {
    await notifyUser.send(successMessage).catch(() => {});
  }

  await interaction.followUp({ content: successMessage, ephemeral: true });
  return true;
}

client.once('ready', async () => {
  console.log(`Logged in as ${client.user.tag}`);
  try {
    await registerCommands();
    console.log('Registered slash commands.');
  } catch (error) {
    console.error('Failed to register slash commands:', error);
  }
});

client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand()) return;

  const username = interaction.options.getString('username');
  const userId = interaction.user.id;

  if (interaction.commandName === 'location') {
    try {
      const locationData = await erlClient.getPlayerLocation(username);
      if (!locationData || locationData.error) {
        await interaction.reply({
          content: `Unable to retrieve location for ${username}: ${locationData?.error ?? 'unknown error'}`,
          ephemeral: true,
        });
        return;
      }

      await interaction.reply({
        content: `Location for ${username}: ${formatLocationData(locationData)}`,
        ephemeral: true,
      });
    } catch (error) {
      await interaction.reply({
        content: `Unable to retrieve location for ${username}.`,
        ephemeral: true,
      });
    }
    return;
  }

  if (interaction.commandName === 'hint') {
    const message = interaction.options.getString('message');
    const hintCommand = message.startsWith(':h') ? message : `:h ${message}`;

    try {
      await erlClient.sendGameHint(hintCommand);
      await interaction.reply({ content: `Sent hint: ${hintCommand}`, ephemeral: true });
    } catch (error) {
      await interaction.reply({ content: `Failed to send hint: ${error.message || error}`, ephemeral: true });
    }
    return;
  }

  if (interaction.commandName === 'kill') {
    const target = interaction.options.getString('target');
    const killCommand = target ? `:kill ${target}` : ':kill';

    try {
      await erlClient.sendGameHint(killCommand);
      await interaction.reply({ content: `Sent kill command: ${killCommand}`, ephemeral: true });
    } catch (error) {
      await interaction.reply({ content: `Failed to send kill command: ${error.message || error}`, ephemeral: true });
    }
    return;
  }

  if (interaction.commandName === 'kill1') {
    const players = await erlClient.getAllPlayerLocations().catch(error => ({ error }));
    if (!Array.isArray(players)) {
      await interaction.reply({ content: `Failed to retrieve player locations: ${players.error || players}`, ephemeral: true });
      return;
    }

    const killZone = {
      xmin: 574.0,
      xmax: 602.0,
      zmin: 2337.0,
      zmax: 2361.0
    };

    const targets = players.filter(player => {
      const location = player.location || {};
      const x = parseFloat(location.LocationX ?? location.locationX ?? location.latitude ?? NaN);
      const z = parseFloat(location.LocationZ ?? location.locationZ ?? location.longitude ?? NaN);
      return !Number.isNaN(x) && !Number.isNaN(z)
        && x >= killZone.xmin && x <= killZone.xmax
        && z >= killZone.zmin && z <= killZone.zmax;
    });

    if (!targets.length) {
      await interaction.reply({ content: `No players found inside the kill zone around 2051 Freedom Avenue.`, ephemeral: true });
      return;
    }

    const killed = [];
    const failed = [];
    for (const player of targets) {
      const username = player.username;
      if (!username) continue;
      const killCommand = `:kill ${username}`;
      try {
        const result = await erlClient.sendGameHint(killCommand);
        if (result?.error) {
          failed.push(`${username} (${result.error})`);
        } else {
          killed.push(username);
        }
      } catch (error) {
        failed.push(`${username} (${error.message || error})`);
      }
    }

    const parts = [];
    if (killed.length) parts.push(`Killed players: ${killed.join(', ')}`);
    if (failed.length) parts.push(`Failed to kill: ${failed.join(', ')}`);
    await interaction.reply({ content: parts.join('\n'), ephemeral: true });
    return;
  }

  if (interaction.commandName !== 'start') return;

  if (activeSessions.has(userId)) {
    await interaction.reply({ content: 'You already have an active challenge.', ephemeral: true });
    return;
  }

  const challengeKey = interaction.options.getString('challenge');
  const missionId = interaction.options.getString('mission');
  const challenge = challengeDefinitions[challengeKey];
  if (!challenge) {
    await interaction.reply({ content: 'Invalid challenge selected.', ephemeral: true });
    return;
  }

  const mission = challenge.missions.find(m => m.id === missionId);
  if (!mission) {
    await interaction.reply({ content: 'That mission does not belong to the selected challenge.', ephemeral: true });
    return;
  }

  activeSessions.add(userId);
  await interaction.reply({ content: `Starting challenge: ${challenge.displayName} — ${mission.name}`, ephemeral: true });

  try {
    await checkArrival(interaction, username, challenge, mission, userId);
  } finally {
    activeSessions.delete(userId);
  }
});

client.login(token).catch(error => {
  console.error('Failed to login:', error);
  process.exit(1);
});
