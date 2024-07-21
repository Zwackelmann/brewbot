import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  loading: false,
  temp: {
    temp_c: null,
    temp_v: null
  },
  error: null,
};


const tempSlice = createSlice({
  name: 'temp',
  initialState,
  reducers: {
    fetchRequest(state) {
      state.loading = true
    },
    fetchSuccess(state, action) {
      state.loading = false
      state.temp.temp_c = action.payload.temp_c
      state.temp.temp_v = action.payload.temp_v
      state.error = null
    },
    fetchFailure(state, action) {
      let error = action.payload
      state.loading = false
      state.error = error
    }
  }
})


export const tempActions = tempSlice.actions;

export default tempSlice.reducer;
