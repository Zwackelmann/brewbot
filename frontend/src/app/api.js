import axios from 'axios';
import qs from 'qs';

const api = {
  listPorts: async () => {
    const response = await axios.get(`/api/list-ports`);
    return response.data;
  },
  initializePort: async (port) => {
    let qValues = {
      baudrate: port.baudrate,
      pins: "1,in,d"
    }
    const response = await axios.get(`/api/${port.name}/new?${qs.stringify(qValues)}`);
    return response.data;
  },
};

export default api;