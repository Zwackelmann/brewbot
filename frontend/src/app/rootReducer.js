import { combineReducers } from '@reduxjs/toolkit';
import tempReducer from '../features/temp/slice';
import heatPlateReducer from '../features/heatPlate/slice';
import motorReducer from '../features/motor/slice';

const rootReducer = combineReducers({
  temp: tempReducer,
  heatPlate: heatPlateReducer,
  motor: motorReducer
});

export default rootReducer;