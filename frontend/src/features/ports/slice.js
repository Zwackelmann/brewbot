import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  loading: false,
  ports: {},
  error: null,
};

function createPort(portName) {
  return {
    name: portName,
    status: 'offline',
    baudrate: 115200,
    session: null,
    operations: {
      initializing: false
    }
  };
}

const portsSlice = createSlice({
  name: 'ports',
  initialState,
  reducers: {
    fetchRequest(state) {
      state.loading = true
    },
    fetchSuccess(state, action) {
      let portNames = action.payload
      state.loading = false
      let portList = portNames.map(createPort)
      state.ports = portList.reduce((portMap, port) => {
        portMap[port.name] = port;
        return portMap;
      }, {});
      state.error = null
    },
    fetchFailure(state, action) {
      let error = action.payload
      state.loading = false
      state.error = error
    },
    initRequest(state, action) {
      let port = action.payload
      console.log("reducer init request")
      console.log(action)
      if(port.name in state.ports) {
        state.ports[port.name].operations.initializing = true
      }
    },
    initSuccess(state, action) {
      const { port, response } = action.payload
      if(port.name in state.ports) {
        state.ports[port.name].operations.initializing = false
        state.ports[port.name].status = 'connected'
        state.ports[port.name].session = response.session
      }
    },
    initFailure(state, action) {
      const { port, error } = action.payload
      if(port.name in state.ports) {
        state.ports[port.name].operations.initializing = false
        state.ports[port.name].status = 'error'
        state.ports[port.name].session = null
      }
    },
  }
})


export const { fetchRequest, fetchSuccess, fetchFailure, initRequest, initSuccess, initFailure } = portsSlice.actions;

export default portsSlice.reducer;

























