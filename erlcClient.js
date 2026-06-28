const axios = require('axios');

class ERLCClient {
  constructor({ baseUrl, apiKey }) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
    this.useErlcDev = baseUrl.includes('erlc.dev');
  }

  async getPlayerLocation(username) {
    if (this.useErlcDev) {
      return {
        error: 'erlc.dev does not provide the live player location API required for /location. Use https://api.erlc.gg with a raw ER:LC server key instead.'
      };
    }

    const apiBase = this.baseUrl.replace(/\/+$/,'');
    const url = `${apiBase}/v2/server`;
    const headers = {
      'Content-Type': 'application/json',
      'server-key': this.apiKey
    };

    const response = await axios.get(url, {
      params: { Players: 'true' },
      headers,
      timeout: 5000
    });

    const data = response.data;
    const players = data.Players || [];
    const player = players.find(p => {
      const playerField = p.Player || '';
      const playerName = playerField.split(':')[0];
      return playerName.toLowerCase() === username.toLowerCase();
    });

    if (!player) {
      return { error: 'Player not found or not in game.' };
    }

    const playerField = player.Player || '';
    const [playerName, playerId] = playerField.split(':');
    return {
      username: playerName,
      id: playerId || null,
      location: player.Location || {}
    };
  }

  async getAllPlayerLocations() {
    if (this.useErlcDev) {
      return { error: 'erlc.dev does not provide live player location data. Use https://api.erlc.gg with a raw ER:LC server key.' };
    }

    const apiBase = this.baseUrl.replace(/\/+$/,'');
    const url = `${apiBase}/v2/server`;
    const headers = {
      'Content-Type': 'application/json',
      'server-key': this.apiKey
    };

    const response = await axios.get(url, {
      params: { Players: 'true' },
      headers,
      timeout: 5000
    });

    const data = response.data;
    const players = data.Players || [];
    return players.map(p => {
      const playerField = p.Player || '';
      const [playerName, playerId] = playerField.split(':');
      return {
        username: playerName,
        id: playerId || null,
        location: p.Location || {}
      };
    });
  }

  async sendGameHint(message) {
    if (this.useErlcDev) {
      return { error: 'Game hint is not supported for erlc.dev API mode.' };
    }

    const apiBase = this.baseUrl.replace(/\/+$/,'');
    const url = `${apiBase}/v1/server/command`;
    const headers = {
      'Content-Type': 'application/json',
      'server-key': this.apiKey
    };

    const response = await axios.post(url, { command: message }, { headers, timeout: 5000 });
    return response.data;
  }
}

module.exports = ERLCClient;
