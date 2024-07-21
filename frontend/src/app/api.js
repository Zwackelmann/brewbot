import axios from 'axios';
import qs from 'qs';

const api = {
  temp: async () => {
    const response = await axios.get(`/api/temp`);
    return response.data;
  },
  heatPlateCmd: (relayState) => (async () => {
    const response = await axios.get(`/api/heat_plate/${relayState}`);
    return response.data;
  }),
  heatPlateState: async () => {
    const response = await axios.get(`/api/heat_plate`);
    return response.data;
  },
  motorCmd: (relayState) => (async () => {
    const response = await axios.get(`/api/motor/${relayState}`);
    return response.data;
  }),
  motorState: async () => {
    const response = await axios.get(`/api/motor`);
    return response.data;
  }
};

export default api;