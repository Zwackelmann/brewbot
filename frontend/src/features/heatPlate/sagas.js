import { call, put, takeEvery } from 'redux-saga/effects';
import axios from 'axios';
import api from '../../app/api';
import { heatPlateActions } from './slice';

function* sendHeatPlateCmdSaga(relayStateAction) {
  try {
    const response = yield call(api.heatPlateCmd(relayStateAction.payload));
    if (response.status === 'success') {
      yield put(heatPlateActions.cmdSuccess(response.data));
    } else if (response.status === 'error') {
      yield put(heatPlateActions.cmdFailure(response.error));
    }
  } catch (error) {
    yield put(heatPlateActions.cmdFailure(error.message));
  }
}

function* fetchHeatPlateStateSaga() {
  try {
    const response = yield call(api.heatPlateState);
    if (response.status === 'success') {
      yield put(heatPlateActions.fetchSuccess(response.data));
    } else if (response.status === 'error') {
      yield put(heatPlateActions.fetchFailure(response.error));
    }
  } catch (error) {
    yield put(heatPlateActions.fetchFailure(error.message));
  }
}

export function* watchSendHeatPlateCmd() {
  yield takeEvery(heatPlateActions.sendCmd.type, sendHeatPlateCmdSaga);
}

export function* watchFetchHeatPlateState() {
  yield takeEvery(heatPlateActions.fetchState.type, fetchHeatPlateStateSaga);
}
