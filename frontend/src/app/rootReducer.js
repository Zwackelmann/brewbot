import { combineReducers } from '@reduxjs/toolkit';
import portsReducer from '../features/ports/slice';

const rootReducer = combineReducers({
  ports: portsReducer
});

export default rootReducer;