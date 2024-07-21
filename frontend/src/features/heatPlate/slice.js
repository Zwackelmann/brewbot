import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  cmd: {
    pending: false,
    data: {
      relay_state: null
    },
    error: null
  },
  state: {
    loading: false,
    data: {
      relay_state: null
    },
    error: null
  }
};


const heatPlateSlice = createSlice({
  name: 'heatPlate',
  initialState,
  reducers: {
    sendCmd(state, action) {
      state.cmd.pending = true
    },
    cmdSuccess(state, action) {
      state.cmd.pending = false
      state.cmd.data = action.payload
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
      state.state.data = action.payload
      state.state.error = null
    },
    fetchFailure(state, action) {
      state.state.loading = false
      state.state.error = action.payload
    }
  }
})

export const heatPlateActions = heatPlateSlice.actions;

export default heatPlateSlice.reducer;
