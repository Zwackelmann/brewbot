import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  cmd: {
    pending: false,
    data: {
      relayState: null
    },
    error: null
  },
  state: {
    loading: false,
    data: {
      relayState: null
    },
    error: null
  }
};


const motorSlice = createSlice({
  name: 'motor',
  initialState,
  reducers: {
    sendCmd(state, action) {
      state.cmd.pending = true
    },
    cmdSuccess(state, action) {
      state.cmd.pending = false
      state.cmd.data.relayState = action.payload.relay_state
      state.cmd.error = null
    },
    cmdFailure(state, action) {
      state.cmd.pending = false
      state.cmd.error = action.payload
    },
    fetchState(state) {
      state.state.loading = true
    },
    fetchSuccess(state, action) {
      state.state.loading = false
      state.state.data.relayState = action.payload.relay_state
      state.state.error = null
    },
    fetchFailure(state, action) {
      state.state.loading = false
      state.state.error = action.payload
    }
  }
})

export const motorActions = motorSlice.actions;

export default motorSlice.reducer;
