import { all } from 'redux-saga/effects';
import { watchFetchTemp } from '../features/temp/sagas';
import { watchSendHeatPlateCmd, watchFetchHeatPlateState } from '../features/heatPlate/sagas';
import { watchSendMotorCmd, watchFetchMotorState } from '../features/motor/sagas';

export default function* rootSaga() {
  yield all([
    watchFetchTemp(),
    watchSendHeatPlateCmd(),
    watchFetchHeatPlateState(),
    watchSendMotorCmd(),
    watchFetchMotorState()
  ]);
}